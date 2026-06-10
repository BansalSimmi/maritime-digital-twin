import React, { useState, useEffect, useRef, useMemo } from 'react';
import api from '../api';

/* ── UI Helpers ── */
const RingGauge = ({ pct, size = 80, stroke = 7, color = '#FF3B3B', children }: any) => {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const dash = circ * Math.min(Math.max(pct, 0) / 100, 1);
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(0,200,255,.10)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color}
          strokeWidth={stroke} strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" style={{ transition: 'stroke-dasharray .9s ease' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>{children}</div>
    </div>
  );
};

const Bar = ({ pct, color = '#FF3B3B' }: any) => (
  <div style={{ height: '4px', background: 'rgba(0,200,255,.08)', borderRadius: '2px', overflow: 'hidden', marginTop: '6px' }}>
    <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width .8s ease' }} />
  </div>
);

const AlertBadge = ({ level }: { level: string }) => {
  const map: Record<string, any> = { CRITICAL: { bg: 'rgba(255,59,59,.18)', c: '#FF3B3B' }, HIGH: { bg: 'rgba(255,140,0,.18)', c: '#FF8C00' }, ELEVATED: { bg: 'rgba(255,187,0,.18)', c: '#FFBB00' }, NORMAL: { bg: 'rgba(0,232,122,.18)', c: '#00E87A' }};
  const s = map[level] || map.NORMAL;
  return <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 8px', borderRadius: '10px', background: s.bg, color: s.c }}>{level}</span>;
};

const SectionHead = ({ title, end, children }: any) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><div style={{ width: 5, height: 5, borderRadius: '50%', background: '#00C8FF', boxShadow: '0 0 6px #00C8FF' }} /><span style={{ fontFamily: 'var(--font)', fontSize: '13px', fontWeight: 700 }}>{title}</span>{end && <span style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--t3)', background: 'var(--bg3)', padding: '2px 7px', borderRadius: '5px' }}>{end}</span>}</div>
    {children}
  </div>
);

/* ── Hooks ── */
function usePoller(intervalMs: number, cb: () => void) {
  const [timeLeft, setTimeLeft] = useState(intervalMs / 1000);
  useEffect(() => { cb(); }, []);
  useEffect(() => {
    const i = setInterval(() => { setTimeLeft(t => { if (t <= 1) { cb(); return intervalMs / 1000; } return t - 1; }); }, 1000);
    return () => clearInterval(i);
  }, [cb, intervalMs]);
  return timeLeft;
}

/* ── Modals ── */
const VesselHistoryModal = ({ mmsi, onClose }: { mmsi: number; onClose: () => void }) => {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.get(`/carbon/vessel/${mmsi}`).then(r => setData(r.data)).catch(()=>setData({error:true})); }, [mmsi]);
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.8)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: 'var(--panel)', border: '1px solid var(--b2)', borderRadius: '14px', width: '100%', maxWidth: '800px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid var(--b)', display: 'flex', justifyContent: 'space-between' }}>
          <div><h2 style={{ fontSize: '18px', fontFamily: 'var(--font)' }}>Vessel {mmsi} Emission History</h2><div style={{ fontSize: '11px', color: 'var(--t2)', marginTop: '4px' }}>{data?.vessel_category} · Type {data?.vessel_type_code}</div></div>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ overflowY: 'auto', padding: '20px' }}>
          {!data ? <div className="lrow"><span className="spin" />Loading…</div> : data.error ? <div className="err-box">Failed to load</div> : (
            <table className="dt">
               <thead><tr><th>Time</th><th>CO₂</th><th>NOx</th><th>SOx</th><th>Speed</th><th>Load</th></tr></thead>
               <tbody>{data.data?.map((d: any, i: number) => <tr key={i}><td style={{color:'var(--t3)'}}>{new Date(d.calculated_at).toLocaleString()}</td><td style={{color:'#FF3B3B', fontFamily: 'var(--mono)'}}>{d.co2_emission}</td><td style={{color:'#00C8FF', fontFamily: 'var(--mono)'}}>{d.nox_emission}</td><td style={{color:'#B47FFF', fontFamily: 'var(--mono)'}}>{d.sox_emission}</td><td style={{fontFamily: 'var(--mono)'}}>{d.speed}kn</td><td style={{fontFamily: 'var(--mono)'}}>{(d.engine_load*100).toFixed(0)}%</td></tr>)}</tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── Calculate Emissions Modal ── */
const CalculateModal = ({ onClose }: { onClose: () => void }) => {
  const [calcMmsi, setCalcMmsi]   = useState('');
  const [vesselType, setVesselType] = useState('');
  const [dateFrom, setDateFrom]   = useState('');
  const [dateTo, setDateTo]       = useState('');
  const [factor, setFactor]       = useState('3.17');
  const [res, setRes]             = useState<any>(null);
  const [running, setRunning]     = useState(false);

  const run = async () => {
    setRunning(true); setRes(null);
    try {
      const payload: any = {};
      if (vesselType) payload.vessel_type = vesselType;
      if (dateFrom)   payload.date_from   = dateFrom;
      if (dateTo)     payload.date_to     = dateTo;
      if (factor)     payload.emission_factor = parseFloat(factor);
      const endpoint = calcMmsi ? `/carbon/calculate/${calcMmsi}` : '/carbon/calculate';
      const r = await api.post(endpoint, payload);
      setRes({ ok: true, data: r.data });
    } catch (e: any) {
      setRes({ ok: false, msg: e?.response?.data?.detail || 'Calculation failed' });
    } finally { setRunning(false); }
  };

  const inp2: React.CSSProperties = { padding: '10px 13px', background: '#0B1D35', border: '1px solid rgba(0,200,255,.15)', borderRadius: '8px', color: '#DFF0FF', fontSize: '13px', outline: 'none', width: '100%', fontFamily: 'DM Sans, sans-serif', transition: 'border-color .2s' };
  const lbl: React.CSSProperties  = { fontSize: '10px', color: '#3A6480', textTransform: 'uppercase', letterSpacing: '.8px', fontWeight: 700, marginBottom: '6px', display: 'block' };
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.78)', backdropFilter: 'blur(8px)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: '#0B1D35', border: '1px solid rgba(0,200,255,.18)', borderRadius: '16px', width: '100%', maxWidth: '560px', boxShadow: '0 32px 80px rgba(0,0,0,.7), 0 0 60px rgba(0,200,255,.05)' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '22px 24px 18px', borderBottom: '1px solid rgba(0,200,255,.1)' }}>
          <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: '18px', fontWeight: 800 }}>Calculate Emissions</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#7AAAC8', fontSize: '18px', cursor: 'pointer', lineHeight: 1 }}>✕</button>
        </div>
        {/* Body */}
        <div style={{ padding: '22px 24px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
            <span style={{ fontSize: '10px', fontWeight: 700, padding: '3px 8px', background: 'rgba(0,232,122,.15)', color: '#00E87A', borderRadius: '5px', letterSpacing: '.5px' }}>POST</span>
            <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '11px', color: '#7AAAC8' }}>/carbon/calculate/{'{'}{'{'}mmsi{'}'}{'}' }</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={lbl}>MMSI Number</label>
              <input style={inp2} placeholder="e.g. 235678901" value={calcMmsi} onChange={e => setCalcMmsi(e.target.value)} />
            </div>
            <div>
              <label style={lbl}>Vessel Type</label>
              <select style={{ ...inp2, cursor: 'pointer' }} value={vesselType} onChange={e => setVesselType(e.target.value)}>
                <option value="">All types</option>
                <option value="70">Cargo (70)</option>
                <option value="80">Tanker (80)</option>
                <option value="60">Passenger (60)</option>
                <option value="30">Fishing (30)</option>
                <option value="50">Diving (50)</option>
              </select>
            </div>
            <div>
              <label style={lbl}>Date From</label>
              <input type="date" style={inp2} value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label style={lbl}>Date To</label>
              <input type="date" style={inp2} value={dateTo} onChange={e => setDateTo(e.target.value)} />
            </div>
          </div>
          <div style={{ marginBottom: '20px' }}>
            <label style={lbl}>Emission Factor (kg/nm)</label>
            <input style={inp2} type="number" step="0.01" value={factor} onChange={e => setFactor(e.target.value)} placeholder="3.17" />
          </div>
          {res && (
            <div style={{ marginBottom: '16px', padding: '12px 14px', borderRadius: '10px', background: res.ok ? 'rgba(0,232,122,.07)' : 'rgba(255,59,59,.07)', border: `1px solid ${res.ok ? 'rgba(0,232,122,.2)' : 'rgba(255,59,59,.2)'}` }}>
              <div style={{ fontSize: '10px', color: '#7AAAC8', marginBottom: '4px' }}>Response</div>
              <pre style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '11px', color: res.ok ? '#00E87A' : '#FF3B3B', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{res.ok ? JSON.stringify(res.data, null, 2) : res.msg}</pre>
            </div>
          )}
          {!res && <div style={{ fontSize: '11px', color: '#3A6480', marginBottom: '16px', padding: '10px 12px', background: 'rgba(0,0,0,.2)', borderRadius: '8px' }}>Response</div>}
        </div>
        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', padding: '16px 24px', borderTop: '1px solid rgba(0,200,255,.1)' }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button onClick={run} disabled={running} style={{ padding: '10px 22px', background: running ? 'rgba(0,232,122,.3)' : 'linear-gradient(135deg,#00C853,#00E87A)', border: 'none', borderRadius: '8px', color: '#001A0D', fontFamily: 'Syne, sans-serif', fontSize: '13px', fontWeight: 700, cursor: running ? 'not-allowed' : 'pointer', opacity: running ? .7 : 1 }}>
            {running ? <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span className="spin" style={{ width: 12, height: 12, borderTopColor: '#001A0D' }} />Running…</span> : 'Run Calculation'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Vessel Profiles Modal ── */
const VesselProfilesModal = ({ onClose }: { onClose: () => void }) => {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState(false);
  useEffect(() => {
    api.get('/carbon/vessel_profiles')
      .then(r => { setProfiles(r.data?.profiles || (Array.isArray(r.data) ? r.data : [])); setLoading(false); })
      .catch(() => { setErr(true); setLoading(false); });
  }, []);
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.78)', backdropFilter: 'blur(8px)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: '#0B1D35', border: '1px solid rgba(0,200,255,.18)', borderRadius: '16px', width: '100%', maxWidth: '920px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', boxShadow: '0 32px 80px rgba(0,0,0,.7)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '22px 24px 18px', borderBottom: '1px solid rgba(0,200,255,.1)', flexShrink: 0 }}>
          <div>
            <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: '18px', fontWeight: 800 }}>Vessel Emission Profiles</h2>
            <div style={{ fontSize: '11px', color: '#7AAAC8', marginTop: '3px' }}>Engine specs · Emission factors · Design speeds &nbsp;·&nbsp; <span style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#00C8FF' }}>/carbon/vessel_profiles</span></div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#7AAAC8', fontSize: '18px', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ overflowY: 'auto', padding: '18px 24px' }}>
          {loading && <div className="lrow"><span className="spin" />Loading profiles…</div>}
          {err    && <div className="err-box">Failed to load profiles</div>}
          {!loading && !err && (
            <table className="dt">
              <thead>
                <tr>
                  <th>Code</th><th>Category</th><th>Design Speed (kn)</th><th>MCR (kW)</th><th>SFC</th>
                  <th>CO₂ Factor</th><th>NOx Factor</th><th>SOx Factor</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((p, i) => (
                  <tr key={i}>
                    <td><span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '10px', padding: '2px 7px', background: 'rgba(0,200,255,.1)', borderRadius: '5px', color: '#00C8FF' }}>{p.vessel_type_code}</span></td>
                    <td style={{ fontWeight: 600, color: '#DFF0FF' }}>{p.vessel_category}</td>
                    <td style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#00FFD4' }}>{p.design_speed}</td>
                    <td style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#00C8FF' }}>{p.mcr_kw}</td>
                    <td style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#7AAAC8' }}>{p.sfc}</td>
                    <td style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#FF3B3B', fontWeight: 700 }}>{p.co2_factor}</td>
                    <td style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#00C8FF' }}>{p.nox_factor}</td>
                    <td style={{ fontFamily: 'IBM Plex Mono, monospace', color: '#B47FFF' }}>{p.sox_factor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '14px 24px', borderTop: '1px solid rgba(0,200,255,.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <span style={{ fontSize: '11px', color: '#3A6480' }}>{profiles.length} profiles loaded</span>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

/* ── Main Component ── */
const Emissions = () => {
  const [fleetSum, setFleetSum]       = useState<any>(null);
  const [alerts, setAlerts]           = useState<any[]>([]);
  const [topPolluters, setTopPolluters] = useState<any[]>([]);
  const [zones, setZones]             = useState<any[]>([]);
  
  const [thresh, setThresh]           = useState('2000');
  const [predMmsi, setPredMmsi]       = useState('');
  const [predRes, setPredRes]         = useState<any>(null);
  const [histMmsi, setHistMmsi]         = useState<number | null>(null);
  const [gaugeMode, setGaugeMode]       = useState<'co2'|'nox'|'sox'>('co2');
  const [showCalc, setShowCalc]         = useState(false);
  const [showProfiles, setShowProfiles] = useState(false);

  const [sortCol, setSortCol] = useState<'co2'|'mmsi'|'speed'>('co2');
  const [sortDesc, setSortDesc] = useState(true);

  // Auto-refresh logic
  const refresh = async () => {
    try {
      const [fs, al, tp, zn] = await Promise.all([
        api.get('/carbon/fleet_summary'),
        api.get(`/carbon/high_emission_alerts?threshold=${thresh}`),
        api.get('/carbon/top_polluters?limit=10'),
        api.get('/carbon/zones')
      ]);
      setFleetSum(fs.data);
      setAlerts(al.data?.alerts || (Array.isArray(al.data) ? al.data : []));
      setTopPolluters(tp.data?.top_polluters || tp.data?.polluters || (Array.isArray(tp.data) ? tp.data : []));
      setZones(zn.data?.zones || []);
    } catch (e) { console.error('Refresh error', e); }
  };
  const timeLeft = usePoller(30000, refresh);

  // Predictions
  const predictEm = async () => {
    if (!predMmsi) return;
    setPredRes({ loading: true });
    try {
      const r = await api.post(`/carbon/predict/${predMmsi}`);
      // Backend returns { predictions_generated: N, predictions: [{...}] }
      const pred = r.data?.predictions?.[0] || r.data;
      if (!pred || pred.loading) throw new Error('empty');
      setPredRes(pred);
    } catch (e: any) {
      setPredRes({ error: e?.response?.data?.detail || 'Prediction failed — check MMSI' });
    }
  };

  // CSV Export
  const exportAlerts = () => {
    if (!alerts.length) return;
    const csv = ['MMSI,Type,CO2_kg_h,NOx_kg_h,SOx_kg_h,Speed,Latitude,Longitude,Level,Time\n']
      .concat(alerts.map(a => `${a.mmsi},${a.vessel_type_code || ''},${a.co2_emission_kg_h},${a.nox_emission_kg_h},${a.sox_emission_kg_h},${a.speed_knots},${a.latitude || ''},${a.longitude || ''},${a.alert_level},${a.time || ''}`))
      .join('\n');
    const u = URL.createObjectURL(new Blob([csv], {type: 'text/csv'}));
    const a = document.createElement('a'); a.href = u; a.download = 'alerts.csv'; a.click();
  };

  // Sorting
  const sortedAlerts = useMemo(() => {
    return [...alerts].sort((a, b) => {
      const vA = sortCol==='co2'?a.co2_emission_kg_h:sortCol==='speed'?a.speed_knots:a.mmsi;
      const vB = sortCol==='co2'?b.co2_emission_kg_h:sortCol==='speed'?b.speed_knots:b.mmsi;
      return sortDesc ? vB - vA : vA - vB;
    });
  }, [alerts, sortCol, sortDesc]);

  // Derived
  const totalCo2  = fleetSum?.total_co2_kg || 0;
  const avgCo2    = fleetSum?.average_co2_kg_h || 0;
  const totalNox  = fleetSum?.total_nox_kg || 0;
  const totalSox  = fleetSum?.total_sox_kg || 0;
  
  // Gauge Config
  const gMax = gaugeMode==='co2'?8000:gaugeMode==='nox'?500:300;
  const gVal = gaugeMode==='co2'?(fleetSum?.peak_co2_kg_h||0):gaugeMode==='nox'?(totalNox/fleetSum?.total_vessels||0): (totalSox/fleetSum?.total_vessels||0);
  const gPct = gVal > 0 ? (gVal / gMax) * 100 : 0;
  const gCol = gaugeMode==='co2'?'#FF3B3B':gaugeMode==='nox'?'#00C8FF':'#B47FFF';
  
  const c = { background: 'var(--panel)', border: '1px solid var(--b)', borderRadius: '14px', padding: '18px', position: 'relative' as any, overflow: 'hidden' };
  const inp = { width: '100%', padding: '9px 13px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: '8px', color: 'var(--text)', fontSize: '12px', outline: 'none', fontFamily: 'var(--mono)' };

  return (
    <div className="page on" id="page-emissions" style={{ paddingBottom: '32px' }}>
      {histMmsi    && <VesselHistoryModal mmsi={histMmsi} onClose={() => setHistMmsi(null)} />}
      {showCalc    && <CalculateModal onClose={() => setShowCalc(false)} />}
      {showProfiles && <VesselProfilesModal onClose={() => setShowProfiles(false)} />}

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <span style={{ fontSize: '22px' }}>🌿</span>
            <h1 style={{ fontFamily: 'var(--font)', fontSize: '22px', fontWeight: 800, letterSpacing: '-.5px' }}>Fleet Carbon Analytics</h1>
            <span style={{ fontSize: '10px', padding: '3px 9px', background: 'rgba(0,200,255,.1)', border: '1px solid rgba(0,200,255,.2)', borderRadius: '12px', color: 'var(--accent)', fontWeight: 700 }}>LIVE</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--t2)' }}>Auto-syncing every 30s · <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>/carbon/</span></div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'6px', background: 'var(--bg3)', padding: '6px 14px', borderRadius: '14px', border: '1px solid var(--b)', fontSize: '11px', color: 'var(--t2)' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: timeLeft > 0 ? 'var(--ok)' : 'var(--warn)', boxShadow: timeLeft > 0 ? '0 0 6px var(--ok)' : '0 0 6px var(--warn)' }} />
            Syncs in <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{Math.floor(timeLeft)}s</span>
          </div>
          {/* ── Action Buttons ── */}
          <button className="btn" onClick={() => setShowProfiles(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>📋</span> Vessel Profiles
          </button>
          <button className="btn prim" onClick={refresh} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>⟳ Force Refresh</button>
        </div>
      </div>

      {/* ── KPI Strip ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '10px', marginBottom: '20px' }}>
        {[
          { label: 'Total CO₂', val: (totalCo2 / 1000).toFixed(1) + ' t', sub: 'fleet cumulative', color: '#FFBB00' },
          { label: 'Avg Rate',  val: Math.round(avgCo2) + '',   sub: 'kg/h per vessel',    color: '#00E87A' },
          { label: 'Peak Rate', val: Math.round(fleetSum?.peak_co2_kg_h||0) + '',  sub: 'kg/h peak vessel', color: '#FF3B3B' },
          { label: 'Total NOx', val: (totalNox / 1000).toFixed(1) + ' t', sub: 'fleet accum',    color: '#00C8FF' },
          { label: 'Total SOx', val: (totalSox / 1000).toFixed(1) + ' t', sub: 'fleet accum',    color: '#B47FFF' },
          { label: 'Avg Speed', val: (fleetSum?.average_speed_knots||0).toFixed(1) + ' kn', sub: 'entire fleet', color: '#00FFD4' }
        ].map(k => (
          <div key={k.label} style={{...c, padding: '14px', boxShadow: '0 0 0 1px rgba(0,200,255,.06), inset 0 1px 0 rgba(0,200,255,.08)'}}>
            <div style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.7px', fontWeight: 700, marginBottom: '8px' }}>{k.label}</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '18px', fontWeight: 700, color: k.color, letterSpacing: '-1px', lineHeight: 1 }}>{k.val}</div>
            <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '5px' }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* ── ROW 1 ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr 320px', gap: '14px', marginBottom: '14px' }}>
        
        {/* Multi-Gauge */}
        <div style={{ ...c, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', background: 'var(--bg3)', borderRadius: '6px', padding: '2px' }}>
            {['co2','nox','sox'].map(m => (
              <button key={m} onClick={()=>setGaugeMode(m as any)} style={{ background: gaugeMode===m?'var(--panel2)':'transparent', border:'none', color: gaugeMode===m?'var(--text)':'var(--t3)', padding:'4px 10px', fontSize:'9px', textTransform:'uppercase', fontWeight:700, borderRadius:'4px', cursor: 'pointer' }}>{m}</button>
            ))}
          </div>
          <RingGauge pct={gPct} size={100} stroke={9} color={gCol}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '16px', fontWeight: 700, color: gCol, lineHeight: 1 }}>{Math.round(gPct)}%</div>
            <div style={{ fontSize: '9px', color: 'var(--t3)', marginTop: '2px' }}>of {gMax} max</div>
          </RingGauge>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '22px', fontWeight: 700, color: gCol }}>{Math.round(gVal)}</div>
            <div style={{ fontSize: '10px', color: 'var(--t3)' }}>emission gauge metric</div>
          </div>
          <div style={{ width: '100%', height: '1px', background: 'var(--b)' }} />
          <div style={{ display:'flex', justifyContent:'space-between', width:'100%', fontSize:'10px', color:'var(--t2)' }}>
             <span>Vessels</span><span style={{fontFamily:'var(--mono)', color:'var(--accent)'}}>{fleetSum?.total_vessels||0}</span>
          </div>
        </div>

        {/* Center: Calculation Engine + Prediction Engine stacked */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

          {/* Calculation Engine */}
          <div style={c}>
            <SectionHead title="Calculation Engine" end="POST /carbon/calculate/{mmsi}">
              <span style={{ fontSize: '9px', padding: '2px 7px', background: 'rgba(0,232,122,.12)', color: '#00E87A', borderRadius: '5px', fontWeight: 700 }}>ENGINE</span>
            </SectionHead>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
              <div>
                <label style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px' }}>MMSI (optional)</label>
                <input id="calc-mmsi" type="number" placeholder="e.g. 229463000" style={inp} />
              </div>
              <div>
                <label style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px' }}>Vessel Type</label>
                <select id="calc-vtype" style={{ ...inp, cursor: 'pointer' }}>
                  <option value="">All types</option>
                  <option value="70">Cargo (70)</option>
                  <option value="80">Tanker (80)</option>
                  <option value="60">Passenger (60)</option>
                  <option value="30">Fishing (30)</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px' }}>Date From</label>
                <input id="calc-from" type="date" style={inp} />
              </div>
              <div>
                <label style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px' }}>Date To</label>
                <input id="calc-to" type="date" style={inp} />
              </div>
            </div>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px' }}>Emission Factor (kg/nm) — default 3.17</label>
              <input id="calc-factor" type="number" step="0.01" defaultValue="3.17" style={inp} />
            </div>
            <button
              onClick={async () => {
                const mmsi   = (document.getElementById('calc-mmsi') as any)?.value;
                const vtype  = (document.getElementById('calc-vtype') as any)?.value;
                const dfrom  = (document.getElementById('calc-from') as any)?.value;
                const dto    = (document.getElementById('calc-to') as any)?.value;
                const factor = (document.getElementById('calc-factor') as any)?.value;
                const payload: any = {};
                if (vtype)  payload.vessel_type      = vtype;
                if (dfrom)  payload.date_from         = dfrom;
                if (dto)    payload.date_to            = dto;
                if (factor) payload.emission_factor   = parseFloat(factor);
                const endpoint = mmsi ? `/carbon/calculate/${mmsi}` : '/carbon/calculate';
                try {
                  const r = await api.post(endpoint, payload);
                  const el = document.getElementById('calc-result')!;
                  el.textContent = JSON.stringify(r.data, null, 2);
                  el.style.color = '#00E87A';
                } catch (e: any) {
                  const el = document.getElementById('calc-result')!;
                  el.textContent = e?.response?.data?.detail || 'Calculation failed';
                  el.style.color = '#FF3B3B';
                }
              }}
              style={{ width: '100%', padding: '10px', background: 'linear-gradient(135deg,#00C853,#00E87A)', border: 'none', borderRadius: '8px', color: '#001A0D', fontFamily: 'var(--font)', fontSize: '12px', fontWeight: 700, cursor: 'pointer', marginBottom: '10px' }}
            >⚡ Run Calculation</button>
            <pre id="calc-result" style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--t3)', background: 'var(--bg3)', borderRadius: '6px', padding: '8px', margin: 0, maxHeight: '80px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>Response will appear here…</pre>
          </div>

          {/* Prediction Engine */}
          <div style={c}>
            <SectionHead title="Prediction Engine" end="POST /carbon/predict/{mmsi}">
              <span style={{ fontSize: '9px', padding: '2px 7px', background: 'rgba(0,200,255,.12)', color: 'var(--accent)', borderRadius: '5px', fontWeight: 700 }}>ML MODEL</span>
            </SectionHead>
            <div style={{ fontSize: '11px', color: 'var(--t2)', marginBottom: '10px', lineHeight: 1.5 }}>
              Predicts future CO₂, NOx &amp; SOx emissions for a vessel based on its current speed, engine load and vessel type profile. Applies a <span style={{ color: 'var(--warn)', fontFamily: 'var(--mono)' }}>1.2×</span> growth factor over a 30-min horizon.
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '8px', marginBottom: '8px' }}>
              <input type="number" placeholder="Enter MMSI e.g. 229463000" value={predMmsi}
                onChange={e => { setPredMmsi(e.target.value); setPredRes(null); }}
                onKeyDown={e => e.key === 'Enter' && predictEm()}
                style={inp} />
              <button className="btn prim" onClick={predictEm} disabled={predRes?.loading}
                style={{ padding: '9px 18px', opacity: predRes?.loading ? .6 : 1, whiteSpace: 'nowrap' }}>
                {predRes?.loading ? <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}><span className="spin" style={{ width: 11, height: 11 }} />Running</span> : '🔮 Predict'}
              </button>
            </div>
            {predRes?.error && <div className="err-box" style={{ fontSize: '11px', marginBottom: '8px' }}>{predRes.error}</div>}
            {predRes && !predRes.loading && !predRes.error && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                {/* Vessel info row */}
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '10px', color: 'var(--t2)' }}>MMSI <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{predRes.mmsi}</span></span>
                  <span style={{ color: 'var(--t3)' }}>·</span>
                  <span style={{ fontSize: '10px', color: 'var(--t2)' }}>Type <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{predRes.vessel_type_code}</span></span>
                  <span style={{ color: 'var(--t3)' }}>·</span>
                  <span style={{ fontSize: '10px', color: 'var(--t2)' }}>Speed <span style={{ fontFamily: 'var(--mono)', color: '#00FFD4' }}>{predRes.current_speed_knots} kn</span></span>
                </div>
                {/* Main CO₂ result */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                  <div style={{ background: 'rgba(255,59,59,.08)', border: '1px solid rgba(255,59,59,.2)', borderRadius: '8px', padding: '10px' }}>
                    <div style={{ fontSize: '9px', color: 'var(--t3)', marginBottom: '4px' }}>Current CO₂</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: 'var(--t2)', fontWeight: 600 }}>{Math.round(predRes.current_co2_kg_h ?? 0)} <span style={{ fontSize: '9px' }}>kg/h</span></div>
                  </div>
                  <div style={{ background: 'rgba(255,59,59,.13)', border: '1px solid rgba(255,59,59,.3)', borderRadius: '8px', padding: '10px' }}>
                    <div style={{ fontSize: '9px', color: 'var(--t3)', marginBottom: '4px' }}>Predicted CO₂ (+30min)</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: '#FF3B3B', fontWeight: 700 }}>{Math.round(predRes.predicted_co2_kg_h ?? 0)} <span style={{ fontSize: '9px' }}>kg/h</span></div>
                  </div>
                  <div style={{ background: 'var(--bg3)', borderRadius: '8px', padding: '10px' }}>
                    <div style={{ fontSize: '9px', color: 'var(--t3)', marginBottom: '4px' }}>Growth Factor</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: 'var(--warn)', fontWeight: 700 }}>{predRes.growth_factor?.toFixed(2)}×</div>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div style={{ background: 'rgba(0,200,255,.06)', border: '1px solid rgba(0,200,255,.15)', borderRadius: '8px', padding: '10px' }}>
                    <div style={{ fontSize: '9px', color: 'var(--t3)', marginBottom: '3px' }}>Predicted NOx</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: '#00C8FF', fontWeight: 700 }}>{Math.round(predRes.predicted_nox_kg_h ?? 0)} <span style={{ fontSize: '9px' }}>kg/h</span></div>
                  </div>
                  <div style={{ background: 'rgba(180,127,255,.06)', border: '1px solid rgba(180,127,255,.15)', borderRadius: '8px', padding: '10px' }}>
                    <div style={{ fontSize: '9px', color: 'var(--t3)', marginBottom: '3px' }}>Predicted SOx</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: '#B47FFF', fontWeight: 700 }}>{Math.round(predRes.predicted_sox_kg_h ?? 0)} <span style={{ fontSize: '9px' }}>kg/h</span></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Top Polluters */}
        <div style={{ ...c, minWidth: 0 }}>
          <SectionHead title="Top Polluters" end="/carbon/top_polluters">
            <span style={{ fontSize: '10px', color: 'var(--t3)' }}>{topPolluters.length} vessels</span>
          </SectionHead>
          {topPolluters.length === 0 ? <div className="lrow"><span className="spin" />Loading…</div> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {topPolluters.map((p, i) => {
                const pct = (fleetSum?.peak_co2_kg_h || 1) > 0 ? (p.total_co2_kg / ((fleetSum?.peak_co2_kg_h||1)*24)) * 100 : 0;
                return (
                  <div key={i} onClick={() => setHistMmsi(p.mmsi)} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '7px 10px', background: 'var(--bg3)', borderRadius: '8px', cursor: 'pointer', transition: 'background .2s' }} onMouseOver={e => { e.currentTarget.style.background='rgba(0,200,255,.05)'; }} onMouseOut={e => { e.currentTarget.style.background='var(--bg3)'; }}>
                    <span style={{ width: '24px', textAlign: 'center', fontSize: i < 3 ? '14px' : '11px', color: 'var(--t3)', fontWeight: 700, flexShrink: 0 }}>{i===0?'🥇':i===1?'🥈':i===2?'🥉':`#${p.rank}`}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', fontWeight: 600, color: 'var(--text)' }}>{p.mmsi}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: '#FF3B3B' }}>{Math.round(p.total_co2_kg).toLocaleString()} kg</span>
                      </div>
                      <Bar pct={pct} color={i < 3 ? '#FF3B3B' : '#FFBB00'} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── ROW 2: Sortable Alerts & Fleet ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: '14px' }}>
        
        {/* Alerts */}
        <div style={c}>
          <SectionHead title="High Emission Alerts" end="/carbon/high_emission_alerts">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button className="btn" onClick={exportAlerts} style={{ padding: '4px 8px', fontSize: '10px' }}>⬇ CSV</button>
              <div style={{ display: 'flex', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: '6px', overflow: 'hidden' }}>
                {['1000','2000','5000'].map(t => (
                  <button key={t} onClick={() => { setThresh(t); setTimeout(refresh, 50); }} style={{ padding: '4px 8px', fontSize: '9px', border: 'none', background: thresh===t?'var(--panel2)':'transparent', color: thresh===t?'var(--accent)':'var(--t3)', cursor: 'pointer' }}>{t}</button>
                ))}
              </div>
            </div>
          </SectionHead>
          {sortedAlerts.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--t3)' }}>✅ No vessels exceed {thresh} kg/h</div>
          ) : (
            <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
              <table className="dt">
                <thead>
                  <tr>
                    <th onClick={()=>{setSortCol('mmsi');setSortDesc(!sortDesc)}} style={{cursor:'pointer'}}>MMSI {sortCol==='mmsi'?(sortDesc?'↓':'↑'):''}</th>
                    <th>Type</th>
                    <th onClick={()=>{setSortCol('co2');setSortDesc(!sortDesc)}} style={{cursor:'pointer'}}>CO₂ {sortCol==='co2'?(sortDesc?'↓':'↑'):''}</th>
                    <th>NOx</th>
                    <th>SOx</th>
                    <th onClick={()=>{setSortCol('speed');setSortDesc(!sortDesc)}} style={{cursor:'pointer'}}>Speed {sortCol==='speed'?(sortDesc?'↓':'↑'):''}</th>
                    <th>Level</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedAlerts.map((a, i) => (
                    <tr key={i} onClick={() => setHistMmsi(a.mmsi)} style={{ cursor: 'pointer' }} onMouseOver={e => e.currentTarget.style.background='rgba(0,200,255,.05)'} onMouseOut={e => e.currentTarget.style.background='transparent'}>
                      <td className="hi">{a.mmsi}</td>
                      <td style={{ color: 'var(--t3)', fontFamily: 'var(--mono)' }}>{a.vessel_type_code || '—'}</td>
                      <td style={{ color: '#FF3B3B', fontFamily: 'var(--mono)', fontWeight: 700 }}>{Math.round(a.co2_emission_kg_h)}</td>
                      <td style={{ color: '#00C8FF', fontFamily: 'var(--mono)' }}>{Math.round(a.nox_emission_kg_h)}</td>
                      <td style={{ color: '#B47FFF', fontFamily: 'var(--mono)' }}>{Math.round(a.sox_emission_kg_h)}</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{a.speed_knots?.toFixed(1)}</td>
                      <td><AlertBadge level={a.alert_level} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Fleet Breakdown & Map Overlay */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{...c, padding: 0, height: '140px', background: 'radial-gradient(ellipse at center, rgba(0,200,255,.05) 0%, transparent 70%) var(--bg2)'}}>
            {/* Super minimal map SVG simulation plotting alerts */}
            <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, opacity: 0.3 }}>
               <path d="M10,40 Q30,10 50,40 T90,40" stroke="var(--b3)" fill="none" />
               <path d="M10,60 Q30,90 50,60 T90,60" stroke="var(--b3)" fill="none" />
            </svg>
            <div style={{ position: 'absolute', inset: 0 }}>
               {sortedAlerts.filter(a=>a.latitude&&a.longitude).slice(0, 30).map((a, i) => {
                  const x = ((a.longitude + 180) / 360) * 100;
                  const y = ((90 - a.latitude) / 180) * 100;
                  return <div key={i} title={a.mmsi.toString()} style={{ position:'absolute', left:`${x}%`, top:`${y}%`, width:4, height:4, background:'#FF3B3B', borderRadius:'50%', boxShadow:'0 0 8px #FF3B3B', transform:'translate(-50%,-50%)' }} />
               })}
            </div>
            <div style={{ position:'absolute', left: 14, bottom: 10, fontSize: '9px', color: 'var(--accent)', fontWeight: 700, letterSpacing:'.5px' }}>EMISSION HOTSPOTS OVERLAY</div>
          </div>
          <div style={{...c, flex: 1}}>
            <SectionHead title="Fleet Profile Dispersion" end="/carbon/fleet_summary" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto', paddingRight: '4px' }}>
              {(fleetSum?.by_vessel_type || []).map((v: any) => {
                const pct = totalCo2 > 0 ? (v.total_co2_kg / totalCo2) * 100 : 0;
                return (
                  <div key={v.vessel_type_code} style={{ padding: '7px 9px', background: 'var(--bg3)', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text)' }}>{v.vessel_category}</div>
                        <div style={{ fontSize: '9px', color: 'var(--t3)', fontFamily: 'var(--mono)' }}>{v.vessels} vessels</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: '#FFBB00', fontWeight: 700 }}>{(v.total_co2_kg/1000).toFixed(1)}t</div>
                      </div>
                    </div>
                    <Bar pct={pct} color="#FFBB00" />
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* ── ROW 3: Geofence Zone Management ── */}
      <div style={{ marginTop: '14px' }}>
        {/* Section title bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <div style={{ width: 3, height: 20, background: 'linear-gradient(180deg,#00C8FF,#B47FFF)', borderRadius: '3px' }} />
          <span style={{ fontFamily: 'var(--font)', fontSize: '15px', fontWeight: 800 }}>Geofence Zone Management</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--t3)', background: 'var(--bg3)', padding: '2px 8px', borderRadius: '5px' }}>/carbon/zones</span>
          <div style={{ flex: 1, height: '1px', background: 'linear-gradient(90deg, var(--b), transparent)' }} />
          <div style={{ display: 'flex', gap: '6px' }}>
            {[
              { method: 'GET',  path: '/carbon/zones',                        label: 'List zones' },
              { method: 'POST', path: '/carbon/zones',                        label: 'Create zone' },
              { method: 'GET',  path: '/carbon/zones/{zone_name}/emissions',  label: 'Zone emissions' },
              { method: 'POST', path: '/carbon/zones/{zone_name}/predict',    label: 'Zone predict' },
            ].map(e => (
              <span key={e.path+e.method} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '9px', color: 'var(--t3)', background: 'var(--bg3)', padding: '3px 7px', borderRadius: '5px', border: '1px solid var(--b)' }}>
                <span style={{ color: e.method==='GET'?'#00C8FF':'#00E87A', fontWeight: 700 }}>{e.method}</span> {e.label}
              </span>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '14px' }}>

          {/* ── Panel 1: Zone List + inline Create (GET + POST /carbon/zones) ── */}
          <ZoneListPanel zones={zones} inp={inp} c={c} refresh={refresh} />

          {/* ── Panel 2: Zone Emissions + Predict result ── */}
          <ZoneResultPanel zones={zones} inp={inp} c={c} />
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────────
   Zone sub-panels (defined after Emissions to avoid hoisting issues)
───────────────────────────────────────────────────────────────────── */

/** GET /carbon/zones — list zones with inline create form ── */
const ZoneListPanel = ({ zones, inp, c, refresh }: any) => {
  const [activeZone, setActiveZone]   = useState<string|null>(null);
  const [zoneData, setZoneData]       = useState<any>(null);
  const [loadingZone, setLoadingZone] = useState(false);
  const [showCreate, setShowCreate]   = useState(false);
  // create-form state
  const [newName, setNewName]         = useState('');
  const [newDesc, setNewDesc]         = useState('');
  const [newGeo, setNewGeo]           = useState('{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}');
  const [creating, setCreating]       = useState(false);
  const [createRes, setCreateRes]     = useState<any>(null);

  const fetchEmissions = async (name: string) => {
    setActiveZone(name); setZoneData(null); setLoadingZone(true);
    try { const r = await api.get(`/carbon/zones/${name}/emissions`); setZoneData({ type: 'emissions', data: r.data }); }
    catch { setZoneData({ error: 'Failed to load emissions' }); }
    finally { setLoadingZone(false); }
  };
  const runPredict = async (name: string) => {
    setActiveZone(name); setZoneData(null); setLoadingZone(true);
    try { const r = await api.post(`/carbon/zones/${name}/predict`); setZoneData({ type: 'predict', data: r.data }); }
    catch { setZoneData({ error: 'Prediction failed' }); }
    finally { setLoadingZone(false); }
  };
  const createZone = async () => {
    if (!newName.trim()) return;
    setCreating(true); setCreateRes(null);
    try {
      let geo: any;
      try { geo = JSON.parse(newGeo); } catch { setCreateRes({ error: 'Invalid GeoJSON' }); setCreating(false); return; }
      await api.post('/carbon/zones', null, { params: { zone_name: newName, description: newDesc, geojson: JSON.stringify(geo) } });
      setCreateRes({ ok: true });
      setNewName(''); setNewDesc('');
      setTimeout(() => { setShowCreate(false); setCreateRes(null); refresh(); }, 1200);
    } catch (e: any) {
      setCreateRes({ error: e?.response?.data?.detail || 'Creation failed' });
    } finally { setCreating(false); }
  };

  const lbl: React.CSSProperties = { fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px', fontWeight: 700 };

  return (
    <div style={c}>
      <SectionHead title="Zone List" end="GET /carbon/zones">
        <div style={{ display: 'flex', gap: '6px' }}>
          <button className="btn" onClick={refresh} style={{ padding: '3px 8px', fontSize: '10px' }}>↺ Reload</button>
          <button onClick={() => { setShowCreate(s => !s); setCreateRes(null); }}
            style={{ padding: '4px 10px', fontSize: '10px', background: showCreate ? 'rgba(0,232,122,.18)' : 'rgba(0,232,122,.08)', border: '1px solid rgba(0,232,122,.3)', borderRadius: '6px', color: '#00E87A', cursor: 'pointer', fontWeight: 700 }}>
            {showCreate ? '✕ Cancel' : '＋ New Zone'}
          </button>
        </div>
      </SectionHead>

      {/* ── Inline Create Form ── */}
      {showCreate && (
        <div style={{ marginBottom: '12px', padding: '12px', background: 'rgba(0,232,122,.04)', border: '1px solid rgba(0,232,122,.15)', borderRadius: '10px' }}>
          <div style={{ fontSize: '10px', color: '#00E87A', fontWeight: 700, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '8px', fontWeight: 700, padding: '2px 6px', background: 'rgba(0,232,122,.2)', borderRadius: '4px' }}>POST</span>
            /carbon/zones
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
            <div>
              <label style={lbl}>Zone Name *</label>
              <input style={inp} placeholder="e.g. harbor_basin" value={newName} onChange={e => setNewName(e.target.value)} />
            </div>
            <div>
              <label style={lbl}>Description</label>
              <input style={inp} placeholder="Optional" value={newDesc} onChange={e => setNewDesc(e.target.value)} />
            </div>
          </div>
          <div style={{ marginBottom: '8px' }}>
            <label style={lbl}>GeoJSON Polygon</label>
            <textarea style={{ ...inp, minHeight: '60px', resize: 'vertical', lineHeight: 1.4 }} value={newGeo} onChange={e => setNewGeo(e.target.value)} />
          </div>
          <button onClick={createZone} disabled={creating || !newName.trim()}
            style={{ width: '100%', padding: '9px', background: creating ? 'rgba(0,232,122,.3)' : 'linear-gradient(135deg,#00C853,#00E87A)', border: 'none', borderRadius: '7px', color: '#001A0D', fontFamily: 'var(--font)', fontSize: '12px', fontWeight: 700, cursor: creating || !newName ? 'not-allowed' : 'pointer', opacity: !newName ? .5 : 1 }}>
            {creating ? <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}><span className="spin" style={{ width: 10, height: 10, borderTopColor: '#001A0D' }} />Creating…</span> : '＋ Create Zone'}
          </button>
          {createRes?.error && <div className="err-box" style={{ marginTop: '6px', fontSize: '11px' }}>{createRes.error}</div>}
          {createRes?.ok && <div style={{ marginTop: '6px', padding: '6px 10px', background: 'rgba(0,232,122,.1)', border: '1px solid rgba(0,232,122,.2)', borderRadius: '5px', fontSize: '11px', color: '#00E87A' }}>✅ Zone created! Refreshing…</div>}
        </div>
      )}

      {zones.length === 0
        ? <div className="lrow"><span className="spin" />Loading zones…</div>
        : <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {zones.map((z: any, i: number) => (
              <div key={i} style={{ background: 'var(--bg3)', borderRadius: '8px', padding: '10px 12px', border: activeZone===z.zone_name ? '1px solid rgba(0,200,255,.3)' : '1px solid transparent', transition: 'border .2s' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', fontWeight: 700, color: 'var(--text)' }}>{z.zone_name}</div>
                    {z.description && <div style={{ fontSize: '10px', color: 'var(--t3)', marginTop: '1px' }}>{z.description}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: '5px', flexShrink: 0 }}>
                    <button onClick={() => fetchEmissions(z.zone_name)}
                      style={{ padding: '4px 9px', fontSize: '9px', background: 'rgba(0,200,255,.1)', border: '1px solid rgba(0,200,255,.2)', borderRadius: '5px', color: '#00C8FF', cursor: 'pointer', fontWeight: 700 }}>
                      📊 Emissions
                    </button>
                    <button onClick={() => runPredict(z.zone_name)}
                      style={{ padding: '4px 9px', fontSize: '9px', background: 'rgba(180,127,255,.1)', border: '1px solid rgba(180,127,255,.2)', borderRadius: '5px', color: '#B47FFF', cursor: 'pointer', fontWeight: 700 }}>
                      🔮 Predict
                    </button>
                  </div>
                </div>
                {activeZone === z.zone_name && (
                  <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(0,0,0,.2)', borderRadius: '6px' }}>
                    {loadingZone && <div className="lrow" style={{ fontSize: '10px' }}><span className="spin" style={{ width: 10, height: 10 }} />Loading…</div>}
                    {zoneData?.error && <div style={{ fontSize: '10px', color: '#FF3B3B' }}>{zoneData.error}</div>}
                    {zoneData && !zoneData.error && !loadingZone && (
                      <div>
                        <div style={{ fontSize: '9px', color: 'var(--accent)', fontWeight: 700, marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '.5px' }}>
                          {zoneData.type === 'emissions' ? '📊 Zone Emissions' : '🔮 Prediction'}
                        </div>
                        {zoneData.type === 'emissions' ? (
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '5px' }}>
                            {[
                              { label: 'Total CO₂', val: `${((zoneData.data?.total_co2_kg || 0)/1000).toFixed(1)}t`, color: '#FF3B3B' },
                              { label: 'Total NOx', val: `${((zoneData.data?.total_nox_kg || 0)/1000).toFixed(1)}t`, color: '#00C8FF' },
                              { label: 'Total SOx', val: `${((zoneData.data?.total_sox_kg || 0)/1000).toFixed(1)}t`, color: '#B47FFF' },
                            ].map(m => (
                              <div key={m.label} style={{ textAlign: 'center' }}>
                                <div style={{ fontSize: '8px', color: 'var(--t3)', marginBottom: '2px' }}>{m.label}</div>
                                <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: m.color, fontWeight: 700 }}>{m.val}</div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <pre style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: '#B47FFF', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {JSON.stringify(zoneData.data, null, 2).slice(0, 300)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
      }
    </div>
  );
};


/** GET /carbon/zones/{zone_name}/emissions + POST /carbon/zones/{zone_name}/predict — side-by-side tabs */
const ZoneResultPanel = ({ zones, inp, c }: any) => {
  const [selectedZone, setSelectedZone] = useState('');
  const [tab, setTab]             = useState<'emissions'|'predict'>('emissions');
  const [result, setResult]       = useState<any>(null);
  const [loading, setLoading]     = useState(false);

  const run = async () => {
    if (!selectedZone) return;
    setLoading(true); setResult(null);
    try {
      const r = tab === 'emissions'
        ? await api.get(`/carbon/zones/${selectedZone}/emissions`)
        : await api.post(`/carbon/zones/${selectedZone}/predict`);
      setResult({ ok: true, data: r.data });
    } catch (e: any) {
      setResult({ error: e?.response?.data?.detail || 'Request failed' });
    } finally { setLoading(false); }
  };

  const methodBadge = (method: string, color: string) => (
    <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 6px', background: `${color}20`, color, borderRadius: '4px', marginRight: '5px' }}>{method}</span>
  );

  return (
    <div style={c}>
      <SectionHead title="Zone Analytics" end="">
        <div style={{ display: 'flex', background: 'var(--bg3)', borderRadius: '6px', padding: '2px' }}>
          <button onClick={() => { setTab('emissions'); setResult(null); }}
            style={{ background: tab==='emissions'?'var(--panel2)':'transparent', border:'none', color: tab==='emissions'?'#00C8FF':'var(--t3)', padding:'4px 10px', fontSize:'9px', fontWeight:700, borderRadius:'4px', cursor:'pointer' }}>
            📊 EMISSIONS
          </button>
          <button onClick={() => { setTab('predict'); setResult(null); }}
            style={{ background: tab==='predict'?'var(--panel2)':'transparent', border:'none', color: tab==='predict'?'#B47FFF':'var(--t3)', padding:'4px 10px', fontSize:'9px', fontWeight:700, borderRadius:'4px', cursor:'pointer' }}>
            🔮 PREDICT
          </button>
        </div>
      </SectionHead>

      {/* Endpoint display */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px', padding: '8px 10px', background: 'var(--bg3)', borderRadius: '6px' }}>
        {tab === 'emissions' ? methodBadge('GET', '#00C8FF') : methodBadge('POST', '#00E87A')}
        <span style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--t2)' }}>
          /carbon/zones/<span style={{ color: '#00C8FF' }}>{selectedZone || '{zone_name}'}</span>/{tab}
        </span>
      </div>

      <div style={{ marginBottom: '12px' }}>
        <label style={{ fontSize: '9px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: '5px', fontWeight: 700 }}>Select Zone</label>
        <select style={{ ...inp, cursor: 'pointer' }} value={selectedZone} onChange={e => { setSelectedZone(e.target.value); setResult(null); }}>
          <option value="">— choose a zone —</option>
          {zones.map((z: any) => <option key={z.zone_name} value={z.zone_name}>{z.zone_name}{z.description ? ` · ${z.description}` : ''}</option>)}
        </select>
      </div>

      <button onClick={run} disabled={loading || !selectedZone}
        style={{ width: '100%', padding: '10px', background: !selectedZone ? 'var(--bg3)' : tab==='emissions' ? 'rgba(0,200,255,.15)' : 'rgba(180,127,255,.15)', border: !selectedZone ? '1px solid var(--b)' : tab==='emissions' ? '1px solid rgba(0,200,255,.3)' : '1px solid rgba(180,127,255,.3)', borderRadius: '8px', color: !selectedZone ? 'var(--t3)' : tab==='emissions' ? '#00C8FF' : '#B47FFF', fontFamily: 'var(--font)', fontSize: '12px', fontWeight: 700, cursor: loading||!selectedZone ? 'not-allowed' : 'pointer', marginBottom: '12px', opacity: !selectedZone ? .5 : 1 }}>
        {loading
          ? <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}><span className="spin" style={{ width: 11, height: 11 }} />Loading…</span>
          : tab === 'emissions' ? `📊 Get Emissions for "${selectedZone||'zone'}"` : `🔮 Predict for "${selectedZone||'zone'}"` }
      </button>

      {/* Results */}
      {result?.error && <div className="err-box" style={{ fontSize: '11px' }}>{result.error}</div>}
      {result?.ok && (
        <div style={{ background: 'var(--bg3)', borderRadius: '8px', padding: '12px' }}>
          {tab === 'emissions' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '10px', color: 'var(--accent)', fontWeight: 700, marginBottom: '2px' }}>
                Zone: <span style={{ fontFamily: 'var(--mono)' }}>{result.data?.zone_name || selectedZone}</span>
                {result.data?.vessel_count != null && <span style={{ marginLeft: '8px', color: 'var(--t2)', fontWeight: 400 }}>{result.data.vessel_count} vessels</span>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                {[
                  { label: 'Total CO₂', val: `${((result.data?.total_co2_kg || 0)/1000).toFixed(2)}t`, color: '#FF3B3B' },
                  { label: 'Total NOx', val: `${((result.data?.total_nox_kg || 0)/1000).toFixed(2)}t`, color: '#00C8FF' },
                  { label: 'Total SOx', val: `${((result.data?.total_sox_kg || 0)/1000).toFixed(2)}t`, color: '#B47FFF' },
                ].map(m => (
                  <div key={m.label} style={{ background: 'rgba(0,0,0,.2)', borderRadius: '6px', padding: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '8px', color: 'var(--t3)', marginBottom: '3px' }}>{m.label}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: m.color, fontWeight: 700 }}>{m.val}</div>
                  </div>
                ))}
              </div>
              {result.data?.avg_co2_kg_h != null && (
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--t2)', padding: '6px 8px', background: 'rgba(0,0,0,.1)', borderRadius: '5px' }}>
                  <span>Avg CO₂/h: <span style={{ fontFamily: 'var(--mono)', color: '#FFBB00' }}>{Math.round(result.data.avg_co2_kg_h)} kg</span></span>
                  {result.data?.peak_co2_kg_h != null && <span>Peak: <span style={{ fontFamily: 'var(--mono)', color: '#FF3B3B' }}>{Math.round(result.data.peak_co2_kg_h)} kg/h</span></span>}
                </div>
              )}
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '10px', color: '#B47FFF', fontWeight: 700, marginBottom: '8px' }}>
                🔮 Predictions for <span style={{ fontFamily: 'var(--mono)' }}>{selectedZone}</span>
              </div>
              <pre style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--t2)', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '180px', overflowY: 'auto' }}>
                {JSON.stringify(result.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Emissions;
