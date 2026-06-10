import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import MapBox from '../components/MapBox';

const PAGE_SIZE = 500;

const ALC: Record<string, string> = {
  NORMAL: 'var(--ok)',
  ELEVATED: 'var(--accent)',
  HIGH: 'var(--warn)',
  CRITICAL: 'var(--danger)',
};

const Tracking = () => {
  const [vessels, setVessels] = useState<any[]>([]);
  const [totalVessels, setTotalVessels] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  // useCallback with page in deps fixes the stale closure issue
  const loadData = useCallback(async (currentPage: number, q: string) => {
    setLoading(true);
    try {
      const res = await api.get(`/api/tracking/live?limit=${PAGE_SIZE}&offset=${currentPage * PAGE_SIZE}${q ? `&q=${encodeURIComponent(q)}` : ''}`);
      let data = res.data?.positions || res.data?.data || res.data?.vessels || res.data || [];
      if (!Array.isArray(data)) data = [];
      setVessels(data);
      setTotalVessels(res.data?.total_vessels ?? res.data?.total ?? data.length);
    } catch (err) {
      console.error('Tracking fetch error', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData(page, search);
    const inv = setInterval(() => loadData(page, search), 30000);
    return () => clearInterval(inv);
  }, [page, search, loadData]);

  const totalPages = Math.ceil(totalVessels / PAGE_SIZE);

  const filtered = vessels;

  const uwCount    = filtered.filter(x => +(x.current_speed || x.speed || 0) > 1).length;
  const alertCount = filtered.filter(x => x.alert_level === 'HIGH' || x.alert_level === 'CRITICAL').length;
  const co2Total   = filtered.reduce((acc, x) => acc + +(x.co2_kg_h || 0), 0);

  const PagBar = () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <button
        className="btn"
        disabled={page === 0}
        onClick={() => setPage(0)}
        style={{ padding: '3px 8px', fontSize: '11px' }}
      >«</button>
      <button
        className="btn"
        disabled={page === 0}
        onClick={() => setPage(p => p - 1)}
        style={{ padding: '3px 8px', fontSize: '11px' }}
      >‹ Prev</button>

      <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text)', padding: '0 6px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: 'var(--r)', height: '26px', display: 'flex', alignItems: 'center' }}>
        Page {page + 1} / {totalPages || '?'}
      </span>

      <button
        className="btn"
        disabled={page + 1 >= totalPages}
        onClick={() => setPage(p => p + 1)}
        style={{ padding: '3px 8px', fontSize: '11px' }}
      >Next ›</button>
      <button
        className="btn"
        disabled={page + 1 >= totalPages}
        onClick={() => setPage(totalPages - 1)}
        style={{ padding: '3px 8px', fontSize: '11px' }}
      >»</button>
    </div>
  );

  return (
    <div className="page on" id="page-tracking">
      {/* Header */}
      <div className="ph">
        <div>
          <div className="pt">Vessel Tracking</div>
          <div className="ps">
            Live AIS positions ·{' '}
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
              GET /api/tracking/live
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <PagBar />
          <input
            type="text"
            placeholder="Search name / MMSI…"
            style={{ padding: '7px 12px', background: 'var(--bg3)', border: '1px solid var(--b)', borderRadius: 'var(--r)', color: 'var(--text)', fontSize: '11px', outline: 'none', width: '200px' }}
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setPage(0); // Reset to first page on search
            }}
          />
          <button className="btn prim" onClick={() => loadData(page)}>⟳ Refresh</button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="g4">
        <div className="sc">
          <div className="sl">Total Fleet</div>
          <div className="sv a">{totalVessels.toLocaleString()}</div>
          <div className="ssub">Pg {page + 1} · {vessels.length} loaded</div>
        </div>
        <div className="sc">
          <div className="sl">Underway</div>
          <div className="sv ok">{uwCount}</div>
          <div className="ssub">speed &gt; 1 kn</div>
        </div>
        <div className="sc">
          <div className="sl">CO₂ Alerts</div>
          <div className="sv d">{alertCount}</div>
          <div className="ssub">HIGH / CRITICAL</div>
        </div>
        <div className="sc">
          <div className="sl">Fleet CO₂</div>
          <div className="sv w">{Math.round(co2Total).toLocaleString()}</div>
          <div className="ssub">kg/h this page</div>
        </div>
      </div>

      {/* Map */}
      <div className="pn" style={{ padding: 0, overflow: 'hidden', marginBottom: '12px' }}>
        <MapBox vessels={filtered} />
      </div>

      {/* Table */}
      <div className="pn">
        <div className="pnh">
          <div className="pnt"><span className="dot"></span>Live Fleet Table</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '10px', color: 'var(--t3)', fontFamily: 'var(--mono)' }}>
              {filtered.length} vessels shown
            </span>
            <div className="pbadge live">● AIS</div>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="dt">
            <thead>
              <tr>
                <th>MMSI</th><th>Vessel Name</th><th>Type</th>
                <th>Speed kn</th><th>Hdg</th><th>Lat</th><th>Lon</th>
                <th>CO₂ kg/h</th><th>Alert</th><th>Scenario</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10}>
                  <div className="lrow"><span className="spin"></span>Fetching live positions…</div>
                </td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={10} style={{ textAlign: 'center', padding: '20px', color: 'var(--t3)' }}>No data</td></tr>
              ) : (
                filtered.map(x => {
                  const spd = +(x.current_speed || x.speed || 0);
                  const hdg = +(x.current_heading || x.heading || 0);
                  const co2 = +(x.co2_kg_h || 0);
                  const al  = x.alert_level || 'NORMAL';
                  const sc  = x.simulation_scenario;
                  const cc  = co2 > 2000 ? 'var(--danger)' : co2 > 1000 ? 'var(--warn)' : 'var(--t2)';
                  return (
                    <tr key={x.mmsi} style={{ cursor: 'pointer' }}>
                      <td className="hi" style={{ fontFamily: 'var(--mono)' }}>{x.mmsi}</td>
                      <td className="hi">{(x.vessel_name || x.name || '—').substring(0, 22)}</td>
                      <td>{x.vessel_type || x.type || '—'}</td>
                      <td style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{spd.toFixed(1)}</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{hdg.toFixed(0)}°</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: '10px' }}>{(+x.latitude).toFixed(4)}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: '10px' }}>{(+x.longitude).toFixed(4)}</td>
                      <td style={{ fontFamily: 'var(--mono)', color: cc }}>{co2 ? Math.round(co2) : '—'}</td>
                      <td>
                        <span style={{ color: ALC[al] || 'var(--t2)', fontSize: '10px', fontWeight: 700 }}>●{al}</span>
                      </td>
                      <td>{sc ? <span className={`tag ${sc}`}>{sc}</span> : '—'}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Bottom pagination bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', padding: '0 4px' }}>
          <span style={{ fontSize: '11px', color: 'var(--t3)', fontFamily: 'var(--mono)' }}>
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, totalVessels)} of {totalVessels.toLocaleString()} vessels
          </span>
          <PagBar />
        </div>
      </div>
    </div>
  );
};

export default Tracking;
