import React, { useEffect, useState } from 'react';
import api from '../api';

const Sidebar = () => {
  const [vessels, setVessels] = useState<any[]>([]);
  const [stats, setStats] = useState({ total: 0, anom: 0, co2a: 0, co2: 0 });

  useEffect(() => {
    const loadSidebarData = async () => {
      try {
        const trk = await api.get('/api/tracking/live');
        let vlist = trk.data?.data || trk.data?.vessels || trk.data?.positions || trk.data || [];
        if (!Array.isArray(vlist)) vlist = [];
        setVessels(vlist);

        const uw = vlist.filter((x: any) => +(x.current_speed || x.speed || 0) > 1).length;
        const al = vlist.filter((x: any) => x.alert_level === 'HIGH' || x.alert_level === 'CRITICAL').length;
        const co2t = vlist.reduce((s: number, x: any) => s + +(x.co2_kg_h || 0), 0);
        
        setStats({
          total: vlist.length,
          anom: al,
          co2a: al,
          co2: Math.round(co2t)
        });
      } catch (err) {
        console.error("Sidebar data fetch error", err);
      }
    };
    loadSidebarData();
    const interval = setInterval(loadSidebarData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="sidebar">
      <div className="ssec">
        <div className="stitle">Fleet Vessels</div>
        <div id="vlist">
          {vessels.length === 0 ? <div className="lrow"><span className="spin"></span>Loading…</div> : null}
          {vessels.slice(0, 25).map(x => {
            const spd = +(x.current_speed || 0);
            const al = x.alert_level || 'NORMAL';
            const st = al === 'CRITICAL' ? 'an' : spd > 1 ? 'uw' : 'ac';
            const stl = al === 'CRITICAL' ? 'ALERT' : spd > 1 ? 'UW' : 'ANCH';
            return (
              <div key={x.mmsi} className="vcard">
                <div className="vcard-h">
                  <div className="vcard-n">{(x.vessel_name || x.name || 'MMSI ' + x.mmsi).substring(0, 16)}</div>
                  <div className={`vs ${st}`}>{stl}</div>
                </div>
                <div className="vmeta">{spd.toFixed(1)}kn · {(+x.latitude).toFixed(2)}°,{(+x.longitude).toFixed(2)}°</div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="ssec">
        <div className="stitle">Quick Stats</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: 'var(--t3)' }}>Total Vessels</span>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{stats.total || '—'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: 'var(--t3)' }}>Active Anomalies</span>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--danger)' }}>{stats.anom || '—'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: 'var(--t3)' }}>CO₂ Alerts</span>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--warn)' }}>{stats.co2a || '—'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: 'var(--t3)' }}>Fleet CO₂ kg/h</span>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--warn)' }}>{stats.co2 || '—'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
