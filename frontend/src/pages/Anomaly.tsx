import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import MapBox from '../components/MapBox';

// #region agent log
const debugLog = (runId: string, hypothesisId: string, location: string, message: string, data: Record<string, unknown>) => {
  fetch('http://127.0.0.1:7591/ingest/6a4ebdf6-2625-4739-90c1-fd53d8f2a2bc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'b9ce97' },
    body: JSON.stringify({
      sessionId: 'b9ce97',
      runId,
      hypothesisId,
      location,
      message,
      data,
      timestamp: Date.now()
    })
  }).catch(() => {});
};
// #endregion

interface AnomalyData {
  anomaly_id: string;
  mmsi: number;
  vessel_name: string;
  anomaly_type: string;
  severity: string;
  description: string;
  latitude: number;
  longitude: number;
  sog: number;
  extra_data: any;
  detected_at: string;
  is_resolved: boolean;
  resolved_at: string | null;
}

interface SummaryData {
  breakdown: { anomaly_type: string; severity: string; active: number; resolved: number; total: number }[];
}

const Anomaly = () => {
  // --- States ---
  const [anomalies, setAnomalies] = useState<AnomalyData[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [mapMarkers, setMapMarkers] = useState<any[]>([]);
  const [totalMapMarkers, setTotalMapMarkers] = useState(0);
  
  // Investigation History Drawer
  const [selectedMmsi, setSelectedMmsi] = useState<number | null>(null);
  const [vesselHistory, setVesselHistory] = useState<AnomalyData[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  
  // Diagnostics Config Modal
  const [showDiagModal, setShowDiagModal] = useState(false);
  const [diagWindow, setDiagWindow] = useState(744); // Default 31 days
  const [diagTypes, setDiagTypes] = useState<string[]>([]);
  
  // Debug / Health Info
  const [debugInfo, setDebugInfo] = useState<any>(null);
  
  // Filters and Pagination
  const [sevF, setSevF] = useState('');
  const [typeF, setTypeF] = useState('');
  const [resolvedF, setResolvedF] = useState(false);
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);

  // Loaders
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);

  // Auto Refresh
  const [autoRefresh, setAutoRefresh] = useState(true);

  // --- API Calls ---
  const fetchDebugInfo = useCallback(async () => {
    try {
      const res = await api.get('/api/anomaly/debug');
      setDebugInfo(res.data);
    } catch (e) {
      console.error("Failed to fetch debug info", e);
    }
  }, []);

  const fetchVesselHistory = async (mmsi: number) => {
    setHistoryLoading(true);
    setSelectedMmsi(mmsi);
    try {
      const res = await api.get(`/api/anomaly/${mmsi}`);
      setVesselHistory(res.data?.anomalies || []);
    } catch (e) {
      console.error("Failed to fetch vessel history", e);
    }
    setHistoryLoading(false);
  };

  const fetchSummary = async () => {
    try {
      const res = await api.get('/api/anomaly/summary');
      setSummary(res.data);
    } catch (e) {
      console.error("Failed to fetch summary", e);
    }
  };

  const fetchMapOverlay = async () => {
    try {
      const res = await api.get('/api/anomaly/map/overlay');
      const markers = res.data?.markers || [];
      // SVG Map freezing fix: Render at most 1000 markers to prevent browser lock-up.
      const mapped = markers.slice(0, 1000).map((m: any) => ({
        mmsi: m.mmsi,
        vessel_name: m.vessel_name || `MMSI ${m.mmsi}`,
        latitude: m.latitude,
        longitude: m.longitude,
        alert_level: m.severity, // MapBox uses alert_level for coloring
        description: m.description,
        anomaly_type: m.anomaly_type
      }));
      setMapMarkers(mapped);
      // We also store total markers to display in the UI map label
      setTotalMapMarkers(markers.length);
    } catch (e) {
      console.error("Failed to fetch map overlay", e);
    }
  };

  const fetchAnomalies = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (sevF) params.append('severity', sevF);
      if (typeF) params.append('anomaly_type', typeF);
      params.append('resolved', resolvedF ? 'true' : 'false');
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const res = await api.get(`/api/anomaly/fleet?${params.toString()}`);
      setAnomalies(res.data?.anomalies || []);
      setTotal(res.data?.total || 0);
      // #region agent log
      debugLog('pre-fix', 'H3', 'frontend/src/pages/Anomaly.tsx:fetchAnomalies', 'Fleet anomalies fetched', {
        total: res.data?.total || 0,
        count: (res.data?.anomalies || []).length,
        resolved: resolvedF,
        severity: sevF || null,
        anomaly_type: typeF || null
      });
      // #endregion
    } catch (e) {
      console.error("Failed to fetch fleet anomalies", e);
      // #region agent log
      debugLog('pre-fix', 'H3', 'frontend/src/pages/Anomaly.tsx:fetchAnomalies', 'Fleet anomalies fetch failed', {
        error: e instanceof Error ? e.message : String(e)
      });
      // #endregion
    }
    setLoading(false);
  }, [sevF, typeF, resolvedF, limit, offset]);

  const loadAll = useCallback(() => {
    fetchSummary();
    fetchMapOverlay();
    fetchAnomalies();
    fetchDebugInfo();
  }, [fetchAnomalies, fetchDebugInfo]);

  // Initial load and Auto-polling
  useEffect(() => {
    loadAll();
    
    let inv: any;
    if (autoRefresh && !detecting) {
      inv = setInterval(loadAll, 15000); // 15s polling
    }
    return () => { if (inv) clearInterval(inv); };
  }, [loadAll, autoRefresh, detecting]);

  const runDetection = async () => {
    if (detecting) return;
    
    if (diagTypes.length === 0) {
      alert("Please select at least one detector algorithm to run the diagnostic pipeline.");
      return;
    }

    setDetecting(true);
    setShowDiagModal(false);
    try {
      // #region agent log
      debugLog('pre-fix', 'H1', 'frontend/src/pages/Anomaly.tsx:runDetection', 'Detection request started', {
        window_hours: diagWindow,
        types_count: diagTypes.length,
        types: diagTypes
      });
      // #endregion
      const params = new URLSearchParams();
      params.append('window_hours', diagWindow.toString());
      params.append('persist', 'true');
      if (diagTypes.length > 0) {
        params.append('types', diagTypes.join(','));
      }
      
      const res = await api.post(`/api/anomaly/detect?${params.toString()}`);
      // #region agent log
      debugLog('pre-fix', 'H2', 'frontend/src/pages/Anomaly.tsx:runDetection', 'Detection response received', {
        total: res.data?.total ?? null,
        persisted: res.data?.persisted ?? null,
        errors_count: Array.isArray(res.data?.errors) ? res.data.errors.length : null
      });
      // #endregion
      loadAll();
    } catch (e) {
      console.error("Failed to run detection", e);
      // #region agent log
      debugLog('pre-fix', 'H1', 'frontend/src/pages/Anomaly.tsx:runDetection', 'Detection request failed', {
        error: e instanceof Error ? e.message : String(e)
      });
      // #endregion
      alert("Error occurred while running detection.");
    }
    setDetecting(false);
  };

  const resolveAnomaly = async (id: string) => {
    try {
      await api.put(`/api/anomaly/${id}/resolve`);
      loadAll();
    } catch (e) {
      console.error("Failed to resolve", e);
    }
  };

  const deleteAnomaly = async (id: string) => {
    if (!window.confirm("Delete this anomaly completely?")) return;
    try {
      await api.delete(`/api/anomaly/${id}`);
      loadAll();
    } catch (e) {
      console.error("Failed to delete", e);
    }
  };

  // --- Summarization processing ---
  let totalActive = 0;
  let critCount = 0;
  let highCount = 0;
  let mediumCount = 0;
  let lowCount = 0;

  if (summary?.breakdown) {
    for (const b of summary.breakdown) {
      totalActive += b.active;
      if (b.severity === 'CRITICAL') critCount += b.active;
      if (b.severity === 'HIGH') highCount += b.active;
      if (b.severity === 'MEDIUM') mediumCount += b.active;
      if (b.severity === 'LOW') lowCount += b.active;
    }
  }

  // Visuals helper
  const getStatus = (sev: string) => {
    if (sev === 'CRITICAL') return 'crit';
    if (sev === 'HIGH') return 'warn';
    if (sev === 'MEDIUM' || sev === 'ELEVATED') return 'info';
    return 'ok';
  };

  return (
    <div className="page on" id="page-anomaly">
      <div className="ph" style={{ marginBottom: '20px' }}>
        <div>
          <div className="pt" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Anomaly Detection Center 
            {autoRefresh && <div className="spill live">Live</div>}
            {debugInfo && (
              <div 
                className="spill info" 
                style={{ fontSize: '9px', padding: '2px 8px', borderColor: 'var(--accent)', color: 'var(--accent)', background: 'rgba(0,200,255,0.05)' }}
                title={`Last AIS sync: ${debugInfo.last_time}`}
              >
                🛰️ {Math.round(debugInfo.ais_count / 1000000)}M Pts Linked
              </div>
            )}
          </div>
          <div className="ps">Real-time maritime anomaly detection & intelligence <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', marginLeft: '8px' }}>/api/anomaly</span></div>
        </div>
        
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--t2)', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={e => setAutoRefresh(e.target.checked)} 
              style={{ accentColor: 'var(--accent)', transform: 'scale(1.1)' }}
            />
            Auto-Sync
          </label>

          <button 
            className="abtn" 
            style={{ padding: '9px 12px', background: 'var(--bg3)', border: '1px solid var(--b)', color: 'var(--t2)', fontSize: '14px' }}
            onClick={() => setShowDiagModal(true)}
            title="Configure Diagnostics"
          >
            ⚙️
          </button>

          <button 
            className="abtn" 
            style={{ padding: '9px 18px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px', opacity: detecting ? 0.7 : 1, pointerEvents: detecting ? 'none' : 'auto' }} 
            onClick={runDetection}
          >
            {detecting ? <span className="spin" style={{ width: '12px', height: '12px', borderWidth: '2px' }}></span> : "▶"}
            {detecting ? 'Scanning...' : 'Run Diagnostics'}
          </button>
        </div>
      </div>

      {/* Split Layout: Top Analytics / Map */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', flexWrap: 'wrap' }}>
        
        {/* Left Stats Column */}
        <div style={{ flex: '1', minWidth: '300px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div className="sc" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
             <div className="sl" style={{ display: 'flex', justifyContent: 'space-between' }}>
               <span>Active Fleet Anomalies</span>
               <span style={{ color: 'var(--t3)' }}>Total Validated</span>
             </div>
             <div className="sv" style={{ fontSize: '32px', display: 'flex', alignItems: 'baseline', gap: '10px' }}>
               {totalActive} <span style={{ fontSize: '12px', color: 'var(--t3)', fontFamily: 'var(--font)', fontWeight: 600 }}>events</span>
             </div>
             <div className="ssub" style={{ marginTop: '8px' }}>Derived from AI behavior models and SQL threshold detectors.</div>
          </div>
          
          <div className="g2" style={{ margin: 0 }}>
            <div className="sc">
              <div className="sl">Critical</div>
              <div className="sv d">{critCount}</div>
            </div>
            <div className="sc">
              <div className="sl">High</div>
              <div className="sv w">{highCount}</div>
            </div>
            <div className="sc">
              <div className="sl">Medium</div>
              <div className="sv a">{mediumCount}</div>
            </div>
            <div className="sc">
              <div className="sl">Low</div>
              <div className="sv ok">{lowCount}</div>
            </div>
          </div>
        </div>

        {/* Right Map Column */}
        <div style={{ flex: '2', minWidth: '400px' }}>
          <div style={{ display: 'flex', gap: '10px', height: '100%' }}>
             <div style={{ flex: 1, position: 'relative', borderRadius: 'var(--rl)', overflow: 'hidden', border: '1px solid var(--b)' }}>
                <MapBox vessels={mapMarkers} />
                <div style={{ position: 'absolute', bottom: '10px', right: '10px', background: 'rgba(5,15,28,.88)', padding: '5px 10px', borderRadius: '6px', fontSize: '10px', color: 'var(--t2)', backdropFilter: 'blur(8px)', border: '1px solid var(--b2)', zIndex: 5 }}>
                  Showing {mapMarkers.length} of {totalMapMarkers || mapMarkers.length} geolocations
                </div>
             </div>
          </div>
        </div>
      </div>

      {/* Feed Area */}
      <div className="pn">
        <div className="pnh">
          <div className="pnt">
             <div className="dot"></div> 
             Anomaly Event Feed
             <span className="pbadge ml" style={{ marginLeft: '8px' }}>{total} found matching filters</span>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Status Tabs */}
            <div style={{ display: 'flex', background: 'var(--bg3)', borderRadius: '6px', border: '1px solid var(--b)', padding: '2px', marginRight: '6px' }}>
              <button 
                onClick={() => { setResolvedF(false); setOffset(0); }} 
                style={{ padding: '6px 12px', fontSize: '11px', border: 'none', background: !resolvedF ? 'var(--panel2)' : 'transparent', color: !resolvedF ? 'var(--text)' : 'var(--t2)', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
              >
                Active
              </button>
              <button 
                onClick={() => { setResolvedF(true); setOffset(0); }} 
                style={{ padding: '6px 12px', fontSize: '11px', border: 'none', background: resolvedF ? 'var(--panel2)' : 'transparent', color: resolvedF ? 'var(--text)' : 'var(--t2)', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
              >
                Resolved
              </button>
            </div>

            <span style={{ fontSize: '11px', color: 'var(--t2)' }}>Severity:</span>
            <select value={sevF} onChange={e => { setSevF(e.target.value); setOffset(0); }} style={{ padding: '6px 10px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: 'var(--r)', color: 'var(--text)', fontSize: '11px', outline: 'none' }}>
              <option value="">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
            
            <span style={{ fontSize: '11px', color: 'var(--t2)' }}>Type:</span>
            <select value={typeF} onChange={e => { setTypeF(e.target.value); setOffset(0); }} style={{ padding: '6px 10px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: 'var(--r)', color: 'var(--text)', fontSize: '11px', outline: 'none' }}>
              <option value="">All Types</option>
              <option value="speed_violation">Speed Violation</option>
              <option value="emission_spike">Emission Spike</option>
              <option value="ais_signal_gap">AIS Signal Gap</option>
              <option value="geofence_breach">Geofence Breach</option>
              <option value="course_deviation">Course Deviation</option>
              <option value="dark_ship">Dark Ship</option>
              <option value="sudden_speed_drop">Sudden Speed Drop</option>
              <option value="draught_change">Draught Change</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="lrow" style={{ justifyContent: 'center', padding: '40px' }}><span className="spin"></span> Syncing with backend...</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '12px' }}>
            {anomalies.length === 0 && (
               <div style={{ padding: '40px', textAlign: 'center', color: 'var(--t3)', gridColumn: '1 / -1' }}>
                 No {resolvedF ? 'resolved' : 'active'} anomalies found matching criteria.
               </div>
            )}
            {anomalies.map((a) => {
              const st = getStatus(a.severity);
              return (
                <div className={`ac ${st}`} key={a.anomaly_id} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div className="ac-h">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className={`abadge ${st}`}>{a.severity}</div>
                      <div className="ac-t">{a.anomaly_type.replace(/_/g, ' ').toUpperCase()}</div>
                    </div>
                    {resolvedF && <div className="vs uw" style={{ fontSize: '8px' }}>RESOLVED</div>}
                  </div>
                  
                  <div className="ac-d" style={{ flex: 1, fontSize: '12px', marginTop: '4px' }}>
                    {a.description || 'Details not provided.'}
                  </div>
                  
                  <div className="ac-m" style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid rgba(0,200,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span>MMSI: <span style={{ fontFamily: 'var(--mono)', color: 'var(--text)', fontWeight: 600 }}>{a.mmsi}</span></span>
                      <span>Vessel: <span style={{ color: 'var(--text)' }}>{a.vessel_name}</span></span>
                      <span>Detected: {new Date(a.detected_at).toLocaleString()}</span>
                    </div>

                    <div style={{ display: 'flex', gap: '6px' }}>
                      {!resolvedF && (
                        <button 
                          onClick={() => resolveAnomaly(a.anomaly_id)}
                          className="btn"
                          style={{ padding: '6px 10px', fontSize: '10px', borderColor: 'var(--ok)', color: 'var(--ok)', background: 'rgba(0,232,122,0.05)' }}
                        >
                          ✓ Resolve
                        </button>
                      )}
                      <button 
                        onClick={() => fetchVesselHistory(a.mmsi)}
                        className="btn"
                        style={{ padding: '6px 10px', fontSize: '10px', borderColor: 'var(--accent)', color: 'var(--accent)', background: 'rgba(0,200,255,0.05)' }}
                      >
                        ⏱ History
                      </button>
                      <button 
                        onClick={() => deleteAnomaly(a.anomaly_id)}
                        className="btn"
                        style={{ padding: '6px 10px', fontSize: '10px', borderColor: 'var(--danger)', color: 'var(--danger)', background: 'rgba(255,59,59,0.05)' }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Server-Side Pagination Controls */}
        {total > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--b)' }}>
            <div style={{ fontSize: '11px', color: 'var(--t2)' }}>
              Showing <span style={{ color: 'var(--text)' }}>{Math.min(offset + 1, total)}</span> to <span style={{ color: 'var(--text)' }}>{Math.min(offset + limit, total)}</span> of <span style={{ color: 'var(--text)', fontFamily: 'var(--mono)', fontWeight: 600 }}>{total}</span> entries
            </div>
            
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <select 
                value={limit} 
                onChange={e => { setLimit(Number(e.target.value)); setOffset(0); }} 
                style={{ padding: '6px 10px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: '6px', color: 'var(--text)', fontSize: '11px', outline: 'none' }}
              >
                <option value="10">10 per page</option>
                <option value="20">20 per page</option>
                <option value="50">50 per page</option>
                <option value="100">100 per page</option>
              </select>

              <button 
                className="btn" 
                onClick={() => setOffset(Math.max(0, offset - limit))} 
                disabled={offset === 0}
                style={{ opacity: offset === 0 ? 0.3 : 1, pointerEvents: offset === 0 ? 'none' : 'auto' }}
              >
                ← Prev
              </button>
              <button 
                className="btn" 
                onClick={() => setOffset(offset + limit)} 
                disabled={offset + limit >= total}
                style={{ opacity: offset + limit >= total ? 0.3 : 1, pointerEvents: offset + limit >= total ? 'none' : 'auto' }}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* --- DIAGNOSTIC MODAL --- */}
      {showDiagModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,5,12,0.85)', backdropFilter: 'blur(8px)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="sc" style={{ width: '100%', maxWidth: '450px', border: '1px solid var(--b2)', padding: '24px', position: 'relative' }}>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '18px' }}>Diagnostic Configuration</h3>
            <p style={{ margin: '0 0 20px 0', color: 'var(--t3)', fontSize: '12px' }}>Select analysis depth and algorithm filters</p>
            
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '11px', color: 'var(--t2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Scan Window depth</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                <button onClick={() => setDiagWindow(24)} style={{ padding: '10px', borderRadius: '6px', border: '1px solid var(--b2)', background: diagWindow === 24 ? 'var(--accent)' : 'var(--bg3)', color: diagWindow === 24 ? '#000' : 'var(--text)', fontSize: '12px', cursor: 'pointer', fontWeight: 600 }}>24 Hours</button>
                <button onClick={() => setDiagWindow(72)} style={{ padding: '10px', borderRadius: '6px', border: '1px solid var(--b2)', background: diagWindow === 72 ? 'var(--accent)' : 'var(--bg3)', color: diagWindow === 72 ? '#000' : 'var(--text)', fontSize: '12px', cursor: 'pointer', fontWeight: 600 }}>3 Days</button>
                <button onClick={() => setDiagWindow(744)} style={{ padding: '10px', borderRadius: '6px', border: '1px solid var(--b2)', background: diagWindow === 744 ? 'var(--accent)' : 'var(--bg3)', color: diagWindow === 744 ? '#000' : 'var(--text)', fontSize: '12px', cursor: 'pointer', fontWeight: 600 }}>31 Days</button>
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                 <div style={{ fontSize: '11px', color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Target Detectors</div>
                 <div style={{ display: 'flex', gap: '8px' }}>
                   <button onClick={() => setDiagTypes(['speed_violation', 'emission_spike', 'ais_signal_gap', 'geofence_breach', 'course_deviation', 'dark_ship', 'sudden_speed_drop', 'draught_change'])} style={{ background: 'transparent', border: 'none', color: 'var(--accent)', fontSize: '10px', cursor: 'pointer', padding: 0 }}>Select All</button>
                   <span style={{ color: 'var(--b3)' }}>|</span>
                   <button onClick={() => setDiagTypes([])} style={{ background: 'transparent', border: 'none', color: 'var(--t3)', fontSize: '10px', cursor: 'pointer', padding: 0 }}>Clear</button>
                 </div>
               </div>
               <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  {['speed_violation', 'emission_spike', 'ais_signal_gap', 'geofence_breach', 'course_deviation', 'dark_ship', 'sudden_speed_drop', 'draught_change'].map(d => (
                    <label key={d} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--t2)', cursor: 'pointer', padding: '6px', background: 'var(--bg2)', borderRadius: '4px', border: diagTypes.includes(d) ? '1px solid rgba(0,200,255,0.3)' : '1px solid transparent' }}>
                      <input 
                        type="checkbox" 
                        checked={diagTypes.includes(d)} 
                        onChange={(e) => {
                          if (e.target.checked) {
                            setDiagTypes([...diagTypes, d]);
                          } else {
                            setDiagTypes(diagTypes.filter(t => t !== d));
                          }
                        }}
                      />
                      {d.replace(/_/g, ' ').toUpperCase()}
                    </label>
                  ))}
               </div>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button className="abtn" style={{ flex: 1 }} onClick={runDetection}>▶ Execute Pipeline</button>
              <button className="btn" style={{ flex: 1 }} onClick={() => setShowDiagModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* --- VESSEL HISTORY DRAWER --- */}
      <div 
        style={{ 
          position: 'fixed', top: 0, right: 0, width: '450px', height: '100vh', 
          background: 'var(--bg)', borderLeft: '1px solid var(--b2)', zIndex: 1001,
          transform: selectedMmsi ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
          boxShadow: '-20px 0 50px rgba(0,0,0,0.5)',
          display: 'flex', flexDirection: 'column'
        }}
      >
        <div style={{ padding: '24px', borderBottom: '1px solid var(--b2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '18px' }}>Investigation: MMSI {selectedMmsi}</h3>
            <div style={{ fontSize: '11px', color: 'var(--accent)' }}>Vessel Historical Anomaly Profile</div>
          </div>
          <button className="btn" onClick={() => setSelectedMmsi(null)} style={{ padding: '8px 12px' }}>CLOSE ✕</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {historyLoading ? (
            <div style={{ padding: '40px', textAlign: 'center' }}><span className="spin"></span> Loading records...</div>
          ) : vesselHistory.length === 0 ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--t3)' }}>No historical anomalies recorded for this vessel.</div>
          ) : (
            vesselHistory.map((h, idx) => (
              <div key={h.anomaly_id} className={`ac ${getStatus(h.severity)}`} style={{ padding: '12px', borderLeftWidth: '3px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text)' }}>#{vesselHistory.length - idx} · {h.anomaly_type.replace(/_/g, ' ')}</span>
                  <span style={{ fontSize: '10px', color: 'var(--t3)' }}>{new Date(h.detected_at).toLocaleDateString()}</span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--t2)', lineHeight: '1.4' }}>{h.description}</div>
                {h.is_resolved && (
                  <div style={{ marginTop: '8px', color: 'var(--ok)', fontSize: '9px', fontWeight: 600 }}>✓ RESOLVED ON {new Date(h.resolved_at!).toLocaleString()}</div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default Anomaly;
