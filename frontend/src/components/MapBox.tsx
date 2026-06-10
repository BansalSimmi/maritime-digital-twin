import React, { useState, useMemo } from 'react';

const ALC: any = { NORMAL: '#00E87A', ELEVATED: '#00C8FF', HIGH: '#FFBB00', CRITICAL: '#FF3B3B' };

interface RouteWaypoint {
  minute: number;
  lat: number;
  lon: number;
  speed: number;
}

interface SimResult {
  mmsi: number;
  scenario: string;
  current_latitude: number;
  current_longitude: number;
  simulated_latitude: number;
  simulated_longitude: number;
  current_speed?: number;
  simulated_speed?: number;
  predicted_route?: RouteWaypoint[];
}

interface MapBoxProps {
  vessels: any[];
  simResult?: SimResult | null;
}

/** Convert lat/lon → SVG pixel coords (full-world projection) */
const ll2svg = (lat: number, lon: number) => ({
  x: ((lon + 180) / 360) * 960,
  y: ((90 - lat) / 180) * 355,
});

const MapBox = ({ vessels, simResult }: MapBoxProps) => {
  const [manualVB, setManualVB] = useState<number[] | null>(null);
  const [popup, setPopup] = useState<{ v: any; x: number; y: number } | null>(null);

  type SimPointType = 'REAL' | 'SIMULATED' | 'WAYPOINT';
  interface SelectedSimPoint { type: SimPointType; title: string; lat: number; lon: number; speed?: number; minute?: number; }
  const [selectedSimPoint, setSelectedSimPoint] = useState<SelectedSimPoint | null>(null);

  // ── Compute focused viewBox around the simulation route ──────────────────
  const autoVB = useMemo<number[]>(() => {
    if (!simResult) return [0, 0, 960, 355];

    // Collect all points: real pos + waypoints + sim pos
    const pts: { x: number; y: number }[] = [];
    if (!isNaN(simResult.current_latitude) && !isNaN(simResult.current_longitude))
      pts.push(ll2svg(simResult.current_latitude, simResult.current_longitude));
    if (!isNaN(simResult.simulated_latitude) && !isNaN(simResult.simulated_longitude))
      pts.push(ll2svg(simResult.simulated_latitude, simResult.simulated_longitude));
    simResult.predicted_route?.forEach(wp => {
      if (!isNaN(wp.lat) && !isNaN(wp.lon)) pts.push(ll2svg(wp.lat, wp.lon));
    });

    if (pts.length === 0) return [0, 0, 960, 355];

    const xs = pts.map(p => p.x);
    const ys = pts.map(p => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    // Ensure a minimum visible window of ~15km (0.4 SVG units)
    const rawW = Math.max(maxX - minX, 0.4);
    const rawH = Math.max(maxY - minY, 0.4);

    // Add 40% padding around the route so markers aren't at the edge
    const padX = rawW * 0.4;
    const padY = rawH * 0.4;

    const vbX = minX - padX;
    const vbY = minY - padY;
    const vbW = rawW + padX * 2;
    const vbH = rawH + padY * 2;

    return [vbX, vbY, vbW, vbH];
  }, [simResult]);

  // Active viewBox: manual override wins, else use auto (focused when sim active, global otherwise)
  const mapVB = manualVB ?? autoVB;

  // Scale-aware sizes: markers & lines should stay visually consistent regardless of zoom
  // vbW relative to full world width (960) gives us a scale factor
  const scale = mapVB[2] / 960;  // < 1 when zoomed in
  const strokeW = 1.5 * scale;           // polyline width
  const dashArr = `${5 * scale},${3 * scale}`; // polyline dashes
  const dotR    = 2.5 * scale;           // waypoint dots
  const markerR = 7 * scale;             // real/sim markers

  const mzoom = (f: number) => {
    if (f === 1) {
      setManualVB(null); // reset back to auto
    } else {
      const vb = manualVB ?? autoVB;
      const cx = vb[0] + vb[2] / 2;
      const cy = vb[1] + vb[3] / 2;
      const nw = vb[2] / f;
      const nh = vb[3] / f;
      setManualVB([cx - nw / 2, cy - nh / 2, nw, nh]);
    }
  };

  // ── Build overlay geometry ───────────────────────────────────────────────
  let routePolyline = '';
  let realPt: { x: number; y: number } | null = null;
  let simPt: { x: number; y: number } | null = null;

  if (simResult) {
    if (!isNaN(simResult.current_latitude) && !isNaN(simResult.current_longitude))
      realPt = ll2svg(simResult.current_latitude, simResult.current_longitude);
    if (!isNaN(simResult.simulated_latitude) && !isNaN(simResult.simulated_longitude))
      simPt = ll2svg(simResult.simulated_latitude, simResult.simulated_longitude);

    if (simResult.predicted_route && simResult.predicted_route.length > 0) {
      const pts = simResult.predicted_route
        .filter(wp => !isNaN(wp.lat) && !isNaN(wp.lon))
        .map(wp => { const p = ll2svg(wp.lat, wp.lon); return `${p.x},${p.y}`; })
        .join(' ');
      routePolyline = realPt ? `${realPt.x},${realPt.y} ${pts}` : pts;
    }
  }

  return (
    <div className="mapbox" id="mapbox" style={{ position: 'relative' }}>
      <svg
        className="mapsvg"
        id="map-svg"
        viewBox={mapVB.join(' ')}
        preserveAspectRatio="xMidYMid meet"
        onClick={() => { setPopup(null); setSelectedSimPoint(null); }}
      >
        <defs>
          <radialGradient id="og" cx="50%" cy="50%">
            <stop offset="0%" stopColor="#041830" />
            <stop offset="100%" stopColor="#020B14" />
          </radialGradient>
          <filter id="glow-cyan" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation={markerR * 0.6} result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-amber" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation={markerR * 0.6} result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Ocean background — covers entire world space */}
        <rect x="-960" y="-355" width="2880" height="1065" fill="url(#og)" />

        {/* Grid lines */}
        <g opacity="0.055" stroke="#00C8FF" strokeWidth="0.4">
          <line x1="0" y1="71" x2="960" y2="71" /><line x1="0" y1="142" x2="960" y2="142" />
          <line x1="0" y1="213" x2="960" y2="213" /><line x1="0" y1="284" x2="960" y2="284" />
          <line x1="192" y1="0" x2="192" y2="355" /><line x1="384" y1="0" x2="384" y2="355" />
          <line x1="576" y1="0" x2="576" y2="355" /><line x1="768" y1="0" x2="768" y2="355" />
        </g>

        {/* Continents */}
        <path d="M18 52 L88 40 L143 56 L168 82 L152 128 L98 146 L48 136 L16 102Z" fill="rgba(18,52,12,.5)" stroke="rgba(28,68,18,.6)" strokeWidth="0.6"/>
        <path d="M18 162 L62 150 L88 170 L80 218 L56 238 L26 216 L14 188Z" fill="rgba(18,52,12,.5)" stroke="rgba(28,68,18,.6)" strokeWidth="0.6"/>
        <path d="M168 26 L308 18 L338 56 L316 102 L288 116 L248 98 L186 76Z" fill="rgba(18,52,12,.5)" stroke="rgba(28,68,18,.6)" strokeWidth="0.6"/>
        <path d="M678 36 L808 23 L876 46 L898 92 L886 156 L840 170 L776 160 L716 136 L678 94Z" fill="rgba(18,52,12,.5)" stroke="rgba(28,68,18,.6)" strokeWidth="0.6"/>
        <path d="M726 206 L803 194 L856 216 L890 253 L868 293 L823 310 L766 303 L726 276 L708 246Z" fill="rgba(18,52,12,.5)" stroke="rgba(28,68,18,.6)" strokeWidth="0.6"/>

        {/* ── Fleet vessel dots ── */}
        <g id="vlayer">
          {vessels.map(v => {
            const lat = +v.latitude;
            const lon = +v.longitude;
            if (isNaN(lat) || isNaN(lon)) return null;
            const { x, y } = ll2svg(lat, lon);
            const al = v.alert_level || 'NORMAL';
            const c = ALC[al] || '#00E87A';
            const r = al === 'CRITICAL' ? 5 : al === 'HIGH' ? 4 : 3;
            return (
              <g key={v.mmsi} onClick={(e) => { e.stopPropagation(); setPopup({ v, x, y }); }} style={{ cursor: 'pointer' }}>
                {al === 'CRITICAL' && <circle cx={x} cy={y} r="10" fill={c} opacity="0.15" />}
                <circle cx={x} cy={y} r={r} fill={c} opacity="0.9" />
              </g>
            );
          })}
        </g>

        {/* ── Simulation overlay ── */}
        {simResult && (
          <g id="sim-overlay">
            {/* Dashed predicted route polyline — drawn first so markers sit on top */}
            {routePolyline && (
              <polyline
                points={routePolyline}
                fill="none"
                stroke="#FFE033"
                strokeWidth={strokeW}
                strokeDasharray={dashArr}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.95"
              />
            )}

            {/* Waypoint dots */}
            {simResult.predicted_route?.filter(wp => !isNaN(wp.lat) && !isNaN(wp.lon)).map((wp, i) => {
              const p = ll2svg(wp.lat, wp.lon);
              return (
                <g
                  key={i}
                  style={{ cursor: 'pointer' }}
                  onClick={(e) => { e.stopPropagation(); setSelectedSimPoint({ type: 'WAYPOINT', title: `Waypoint +${wp.minute} min`, lat: wp.lat, lon: wp.lon, speed: wp.speed, minute: wp.minute }); }}
                >
                  <circle cx={p.x} cy={p.y} r={dotR * 2.5} fill="transparent" /> {/* larger hit area */}
                  <circle cx={p.x} cy={p.y} r={dotR} fill="#FFE033" opacity="0.9" stroke="rgba(255,255,255,0.6)" strokeWidth={strokeW * 0.3} />
                  <title>+{wp.minute} min · {wp.speed?.toFixed(1)} kn · {wp.lat.toFixed(3)}°, {wp.lon.toFixed(3)}°</title>
                </g>
              );
            })}

            {/* Real position — cyan pulsing beacon */}
            {realPt && (
              <g onClick={(e) => { e.stopPropagation(); setSelectedSimPoint({ type: 'REAL', title: 'Real Position', lat: simResult.current_latitude, lon: simResult.current_longitude, speed: simResult.current_speed }); }} style={{ cursor: 'pointer' }}>
                <circle cx={realPt.x} cy={realPt.y} r={markerR * 2} fill="#00C8FF" opacity="0.12" className="pulse" />
                <circle cx={realPt.x} cy={realPt.y} r={markerR} fill="#00C8FF" opacity="0.95" filter="url(#glow-cyan)" />
                <circle cx={realPt.x} cy={realPt.y} r={markerR * 0.35} fill="#fff" opacity="0.95" />
              </g>
            )}

            {/* Simulated position — amber beacon */}
            {simPt && (
              <g onClick={(e) => { e.stopPropagation(); setSelectedSimPoint({ type: 'SIMULATED', title: `Simulated Position (${simResult.scenario})`, lat: simResult.simulated_latitude, lon: simResult.simulated_longitude, speed: simResult.simulated_speed }); }} style={{ cursor: 'pointer' }}>
                <circle cx={simPt.x} cy={simPt.y} r={markerR * 2} fill="#FF8C00" opacity="0.12" className="pulse" />
                <circle cx={simPt.x} cy={simPt.y} r={markerR} fill="#FF8C00" opacity="0.95" filter="url(#glow-amber)" />
                <circle cx={simPt.x} cy={simPt.y} r={markerR * 0.35} fill="#fff" opacity="0.95" />
              </g>
            )}
          </g>
        )}
      </svg>

      {/* Overlay status */}
      <div className="movl">
        <div className="mlbl">🛰 AIS + Digital Twin</div>
        <div className="mlbl" id="map-ts">
          {simResult ? `Sim: MMSI ${simResult.mmsi} · ${simResult.scenario}` : 'Live Active'}
        </div>
      </div>

      {/* Bottom legend when sim is active */}
      {simResult && (
        <div style={{
          position: 'absolute',
          bottom: '44px',
          left: '10px',
          background: 'rgba(4,24,48,0.88)',
          border: '1px solid rgba(0,200,255,0.2)',
          borderRadius: '6px',
          padding: '6px 10px',
          display: 'flex',
          gap: '12px',
          fontSize: '10px',
          color: 'var(--t2)',
          backdropFilter: 'blur(6px)',
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="#00C8FF"/></svg>
            Real
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="#FF8C00"/></svg>
            Simulated
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <svg width="18" height="8">
              <line x1="0" y1="4" x2="18" y2="4" stroke="#FFE033" strokeWidth="2" strokeDasharray="5,3"/>
            </svg>
            Route ({simResult.predicted_route?.length ?? 0} pts)
          </span>
        </div>
      )}

      {/* Zoom controls */}
      <div className="mctrl">
        <div className="mbtn" onClick={() => mzoom(1.5)} title="Zoom In">+</div>
        <div className="mbtn" onClick={() => mzoom(0.67)} title="Zoom Out">−</div>
        <div className="mbtn" onClick={() => mzoom(1)} title="Reset / Re-centre">⊙</div>
      </div>

      {/* Vessel popup */}
      {popup && (
        <div id="vpopup" style={{ display: 'block', pointerEvents: 'auto', left: '10px', top: '10px' }}>
          <div style={{ fontFamily: 'var(--font)', fontSize: '12px', fontWeight: 700, marginBottom: '5px' }}>
            {popup.v.vessel_name || popup.v.name || 'MMSI ' + popup.v.mmsi}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t2)', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <span>MMSI: <span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{popup.v.mmsi}</span></span>
            <span>Speed: <span style={{ color: 'var(--accent)' }}>{(+(popup.v.current_speed || 0)).toFixed(1)} kn</span></span>
            <span>CO₂: <span style={{ color: 'var(--warn)' }}>{popup.v.co2_kg_h ? Math.round(popup.v.co2_kg_h) : '—'} kg/h</span></span>
            <span>Alert: <span style={{ color: ALC[popup.v.alert_level || 'NORMAL'] }}>{popup.v.alert_level || 'NORMAL'}</span></span>
            {popup.v.anomaly_type && (
              <span>Anomaly: <span style={{ color: 'var(--warn)' }}>{popup.v.anomaly_type.replace(/_/g, ' ').toUpperCase()}</span></span>
            )}
            {popup.v.description && (
              <span style={{ marginTop: '2px', lineHeight: '1.3', padding: '4px', background: 'rgba(255,59,59,0.1)', border: '1px solid rgba(255,59,59,0.2)', borderRadius: '4px' }}>
                {popup.v.description}
              </span>
            )}
          </div>
          <button
            onClick={() => setPopup(null)}
            style={{ pointerEvents: 'auto', marginTop: '7px', width: '100%', padding: '5px', background: 'rgba(0,200,255,.1)', border: '1px solid var(--b2)', borderRadius: '5px', color: 'var(--accent)', cursor: 'pointer', fontSize: '10px' }}
          >Close</button>
        </div>
      )}

      {/* Simulation Point tooltip popup */}
      {selectedSimPoint && (
        <div style={{
          position: 'absolute',
          left: '10px',
          top: '10px',
          background: 'rgba(4,24,48,0.94)',
          border: `1px solid ${selectedSimPoint.type === 'REAL' ? 'rgba(0,200,255,0.45)' : selectedSimPoint.type === 'SIMULATED' ? 'rgba(255,140,0,0.45)' : 'rgba(255,224,51,0.45)'}`,
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '11px',
          color: 'var(--text)',
          pointerEvents: 'auto',
          zIndex: 10,
          minWidth: '140px',
        }}>
          <div style={{ fontWeight: 700, color: selectedSimPoint.type === 'REAL' ? '#00C8FF' : selectedSimPoint.type === 'SIMULATED' ? '#FF8C00' : '#FFE033', marginBottom: '4px' }}>
            {selectedSimPoint.title}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--t2)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span>Lat: <span style={{ fontFamily: 'var(--mono)', color: '#fff' }}>{selectedSimPoint.lat.toFixed(4)}°</span></span>
            <span>Lon: <span style={{ fontFamily: 'var(--mono)', color: '#fff' }}>{selectedSimPoint.lon.toFixed(4)}°</span></span>
            <span>Speed: <span style={{ color: 'var(--accent)' }}>{selectedSimPoint.speed !== undefined ? selectedSimPoint.speed.toFixed(1) : '—'} kn</span></span>
          </div>
          <button
            onClick={() => setSelectedSimPoint(null)}
            style={{ marginTop: '6px', width: '100%', padding: '4px', background: selectedSimPoint.type === 'REAL' ? 'rgba(0,200,255,.1)' : selectedSimPoint.type === 'SIMULATED' ? 'rgba(255,140,0,.1)' : 'rgba(255,224,51,.1)', border: `1px solid ${selectedSimPoint.type === 'REAL' ? 'rgba(0,200,255,.3)' : selectedSimPoint.type === 'SIMULATED' ? 'rgba(255,140,0,.3)' : 'rgba(255,224,51,.3)'}`, borderRadius: '4px', color: selectedSimPoint.type === 'REAL' ? '#00C8FF' : selectedSimPoint.type === 'SIMULATED' ? '#FF8C00' : '#FFE033', cursor: 'pointer', fontSize: '10px' }}
          >✕ Close</button>
        </div>
      )}
    </div>
  );
};

export default MapBox;
