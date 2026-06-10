import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import MapBox from '../components/MapBox';

const PAGE_SIZE = 500;

const DigitalTwin = () => {
  const [simMmsi, setSimMmsi] = useState('');
  const [scenario, setScenario] = useState('AUTO');
  const [ahead, setAhead] = useState('120');
  const [step, setStep] = useState('20');
  const [simRes, setSimRes] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [twins, setTwins] = useState<any[]>([]);
  const [twinsTotal, setTwinsTotal] = useState(0);
  const [showMap, setShowMap] = useState(true);
  const [page, setPage] = useState(0);

  const runSim = async () => {
    if (!simMmsi) return;
    setLoading(true);
    setSimRes(null);
    try {
      const payload = {
        mmsi: parseInt(simMmsi),
        scenario,
        minutes_ahead: parseInt(ahead),
        step_minutes: parseInt(step)
      };
      const res = await api.post('/twin/digital-twin/simulate', payload);
      setSimRes(res.data);
      setShowMap(true); // auto-show map on new result
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join('\n')
          : e.message || 'Simulation Failed';
      setSimRes({ error: msg });
    }
    setLoading(false);
  };

  const syncAll = async () => {
    setLoading(true);
    try {
      const res = await api.post('/twin/digital-twin/sync', {
        minutes_ahead: parseInt(ahead),
        step_minutes: parseInt(step)
      });
      setSimRes({ syncResult: res.data });
    } catch (e: any) {
      setSimRes({ error: e.response?.data?.detail || e.message });
    }
    setLoading(false);
  };

  const loadTwinV = useCallback(async (currentPage: number) => {
    try {
      const res = await api.get(`/twin/digital-twin/vessels?limit=${PAGE_SIZE}&offset=${currentPage * PAGE_SIZE}`);
      setTwins(res.data?.vessels || []);
      setTwinsTotal(res.data?.total || 0);
    } catch (e: any) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadTwinV(page);
  }, [page, loadTwinV]);

  const totalPages = Math.ceil(twinsTotal / PAGE_SIZE);

  const PagBar = () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <button className="btn" disabled={page === 0} onClick={() => setPage(0)} style={{ padding: '3px 8px', fontSize: '11px' }}>«</button>
      <button className="btn" disabled={page === 0} onClick={() => setPage(p => p - 1)} style={{ padding: '3px 8px', fontSize: '11px' }}>‹ Prev</button>
      <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text)', padding: '0 6px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: 'var(--r)', height: '26px', display: 'flex', alignItems: 'center' }}>
        Page {page + 1} / {totalPages || '?'}
      </span>
      <button className="btn" disabled={page + 1 >= totalPages} onClick={() => setPage(p => p + 1)} style={{ padding: '3px 8px', fontSize: '11px' }}>Next ›</button>
      <button className="btn" disabled={page + 1 >= totalPages} onClick={() => setPage(totalPages - 1)} style={{ padding: '3px 8px', fontSize: '11px' }}>»</button>
    </div>
  );

  const fmtCoord = (v: number | null | undefined) =>
    v != null ? v.toFixed(4) : '—';

  // Build a simResult compatible with MapBox's SimResult interface
  const mapSimResult = simRes?.mmsi ? {
    mmsi: simRes.mmsi,
    scenario: simRes.scenario,
    current_latitude: simRes.current_latitude,
    current_longitude: simRes.current_longitude,
    simulated_latitude: simRes.simulated_latitude,
    simulated_longitude: simRes.simulated_longitude,
    current_speed: simRes.current_speed,
    simulated_speed: simRes.simulated_speed,
    predicted_route: simRes.predicted_route || [],
  } : null;

  return (
    <div className="page on" id="page-twin">
      <div className="ph">
        <div>
          <div className="pt">Digital Twin Simulation</div>
          <div className="ps">Run scenarios · <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>POST /twin/digital-twin/simulate</span></div>
        </div>
      </div>

      <div className="g2">
        {/* ── Left: Simulation Form ── */}
        <div className="pn">
          <div className="pnh"><div className="pnt"><span className="dot"></span>Simulation Request</div></div>

          <div className="srow">
            <div className="slbl"><span>Vessel MMSI</span></div>
            <input
              type="number"
              placeholder="e.g. 209550000"
              value={simMmsi}
              onChange={e => setSimMmsi(e.target.value)}
              style={{ width: '100%', padding: '9px 12px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: 'var(--r)', color: 'var(--text)', fontSize: '13px', outline: 'none' }}
            />
          </div>

          <div className="srow" style={{ marginTop: '10px' }}>
            <div className="slbl"><span>Scenario</span></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              {['AUTO', 'NORMAL', 'STORM', 'DETOUR'].map(s => (
                <button
                  key={s}
                  className={`btn ${scenario === s ? 'prim' : ''}`}
                  onClick={() => setScenario(s)}
                >
                  {s === 'STORM' ? '⛈ STORM' : s === 'DETOUR' ? '🔀 DETOUR' : s}
                </button>
              ))}
            </div>
          </div>

          <div className="srow" style={{ marginTop: '10px' }}>
            <div className="slbl">
              <span>Minutes Ahead</span>
              <span className="sval">{ahead} min</span>
            </div>
            <input type="range" min="20" max="1440" value={ahead} onChange={e => setAhead(e.target.value)} />
          </div>

          <div className="srow">
            <div className="slbl">
              <span>Step Minutes</span>
              <span className="sval">{step} min</span>
            </div>
            <input type="range" min="1" max="60" value={step} onChange={e => setStep(e.target.value)} />
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button
              className="abtn"
              style={{ flex: 1, padding: '10px', fontSize: '13px' }}
              onClick={runSim}
              disabled={loading || !simMmsi}
            >
              {loading ? '⏳ Simulating…' : '▶ Run Simulation'}
            </button>
            <button className="btn" onClick={syncAll} disabled={loading}>Sync All</button>
          </div>
        </div>

        {/* ── Right: Result ── */}
        <div className="pn">
          <div className="pnh">
            <div className="pnt"><span className="dot"></span>Simulation Result</div>
            {mapSimResult && (
              <button
                className={`btn ${showMap ? 'prim' : ''}`}
                onClick={() => setShowMap(v => !v)}
                style={{ padding: '4px 10px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                🗺 {showMap ? 'Hide Map' : 'Show on Map'}
              </button>
            )}
          </div>
          <div id="sim-res">
            {loading && <div className="lrow"><span className="spin"></span>Running simulation…</div>}

            {!loading && !simRes && (
              <div style={{ fontSize: '12px', color: 'var(--t3)', textAlign: 'center', padding: '30px 0' }}>
                Enter an MMSI, pick a scenario, then click ▶ Run Simulation
              </div>
            )}

            {simRes?.error && (
              <div className="err-box" style={{ whiteSpace: 'pre-wrap' }}>{simRes.error}</div>
            )}

            {simRes?.syncResult && (
              <div className="ok-box">
                Sync complete — {simRes.syncResult.simulated} vessels simulated,{' '}
                {simRes.syncResult.skipped} skipped.
              </div>
            )}

            {simRes?.mmsi && (
              <div>
                <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ background: 'rgba(0,200,255,.12)', border: '1px solid var(--b2)', borderRadius: '5px', padding: '3px 10px', fontSize: '11px', fontFamily: 'var(--mono)' }}>
                    MMSI {simRes.mmsi}
                  </span>
                  <span style={{ background: 'rgba(0,232,122,.12)', border: '1px solid var(--ok)', borderRadius: '5px', padding: '3px 10px', fontSize: '11px', color: 'var(--ok)' }}>
                    {simRes.scenario}
                  </span>
                </div>
                <div className="code" style={{ fontSize: '11px', lineHeight: '1.8' }}>
                  <span className="ck">Real Position:</span>{' '}
                  <span className="cv">{fmtCoord(simRes.current_latitude)}°, {fmtCoord(simRes.current_longitude)}°</span><br />
                  <span className="ck">Real Speed:</span>{' '}
                  <span className="cv">{simRes.current_speed?.toFixed(1) ?? '—'} kn</span><br />
                  <span className="ck">Heading:</span>{' '}
                  <span className="cv">{simRes.current_heading?.toFixed(0) ?? '—'}°</span><br />
                  <br />
                  <span className="ck">Sim Position:</span>{' '}
                  <span className="cs">{fmtCoord(simRes.simulated_latitude)}°, {fmtCoord(simRes.simulated_longitude)}°</span><br />
                  <span className="ck">Sim Speed:</span>{' '}
                  <span className="cs">{simRes.simulated_speed?.toFixed(1) ?? '—'} kn</span><br />
                  <br />
                  <span className="ck">Waypoints:</span>{' '}
                  <span className="cv">{simRes.predicted_route?.length ?? 0} points</span><br />
                  <span className="ck">Sim Time:</span>{' '}
                  <span className="cv">{simRes.simulation_time ? new Date(simRes.simulation_time).toLocaleTimeString() : '—'}</span>
                </div>

                {simRes.predicted_route?.length > 0 && (
                  <div style={{ marginTop: '10px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--t3)', marginBottom: '5px' }}>PREDICTED ROUTE WAYPOINTS</div>
                    <div style={{ maxHeight: '150px', overflowY: 'auto', fontSize: '10px', fontFamily: 'var(--mono)' }}>
                      <table className="dt" style={{ fontSize: '10px' }}>
                        <thead><tr><th>+min</th><th>Lat</th><th>Lon</th><th>kn</th></tr></thead>
                        <tbody>
                          {simRes.predicted_route.map((wp: any, i: number) => (
                            <tr key={i}>
                              <td>+{wp.minute}</td>
                              <td>{wp.lat?.toFixed(4)}</td>
                              <td>{wp.lon?.toFixed(4)}</td>
                              <td>{wp.speed?.toFixed(1)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Simulation Map ── */}
      {mapSimResult && showMap && (
        <div
          className="pn"
          style={{ padding: 0, overflow: 'hidden', marginBottom: '12px' }}
          id="sim-map-panel"
        >
          <div className="pnh" style={{ padding: '8px 14px' }}>
            <div className="pnt">
              <span className="dot"></span>
              Simulation Map
              <span style={{ fontSize: '10px', color: 'var(--t3)', fontFamily: 'var(--mono)', marginLeft: '8px' }}>
                MMSI {mapSimResult.mmsi} · {mapSimResult.predicted_route?.length ?? 0} waypoints
              </span>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', fontSize: '10px', color: 'var(--t2)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#00C8FF', display: 'inline-block' }}></span> Real
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#FF8C00', display: 'inline-block' }}></span> Simulated
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <svg width="18" height="8">
                  <line x1="0" y1="4" x2="18" y2="4" stroke="#FFB800" strokeWidth="2" strokeDasharray="4,2"/>
                </svg> Route
              </span>
            </div>
          </div>
          <MapBox vessels={[]} simResult={mapSimResult} />
        </div>
      )}

      {/* ── Vessel Twin States table ── */}
      <div className="pn">
        <div className="pnh">
          <div className="pnt">
            <span className="dot"></span>All Vessel Twin States
            <span style={{ fontSize: '9px', color: 'var(--t3)', fontFamily: 'var(--mono)', marginLeft: '6px' }}>
              /twin/digital-twin/vessels
            </span>
            {twinsTotal > 0 && (
              <span style={{ fontSize: '10px', color: 'var(--accent)', marginLeft: '8px' }}>
                {twinsTotal.toLocaleString()} total
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <PagBar />
            <button className="btn prim" onClick={() => loadTwinV(page)}>⟳ Refresh</button>
          </div>
        </div>

        {twins.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--t3)', padding: '10px', textAlign: 'center' }}>
            No vessels found.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="dt">
              <thead>
                <tr>
                  <th>MMSI</th>
                  <th>Scenario</th>
                  <th>Real Pos</th>
                  <th>Sim Pos</th>
                  <th>Speed kn</th>
                  <th>Sim Speed</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {twins.map((t, idx) => (
                  <tr key={idx}>
                    <td className="hi" style={{ fontFamily: 'var(--mono)' }}>{t.mmsi}</td>
                    <td>{t.simulation_scenario || '—'}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: '10px' }}>
                      {fmtCoord(t.latitude)}°,{fmtCoord(t.longitude)}°
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--accent)' }}>
                      {fmtCoord(t.simulated_latitude)}°,{fmtCoord(t.simulated_longitude)}°
                    </td>
                    <td style={{ fontFamily: 'var(--mono)' }}>{t.current_speed?.toFixed(1) ?? '—'}</td>
                    <td style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{t.simulated_speed?.toFixed(1) ?? '—'}</td>
                    <td style={{ fontSize: '10px', color: 'var(--t3)' }}>
                      {t.last_update ? new Date(t.last_update).toLocaleTimeString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', padding: '0 4px' }}>
              <span style={{ fontSize: '11px', color: 'var(--t3)', fontFamily: 'var(--mono)' }}>
                Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, twinsTotal)} of {twinsTotal.toLocaleString()} vessels
              </span>
              <PagBar />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DigitalTwin;
