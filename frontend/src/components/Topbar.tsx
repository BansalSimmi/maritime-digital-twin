import React, { useEffect, useState, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../context/AuthContext';
import { LogOut, User as UserIcon, Settings } from 'lucide-react';

const Topbar = () => {
  const [apiStatus, setApiStatus] = useState<'LIVE' | 'OFFLINE'>('LIVE');
  const [anomalyCount, setAnomalyCount] = useState(0);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Determine API status
    api.get('/').then(() => setApiStatus('LIVE')).catch(() => setApiStatus('OFFLINE'));

    // Fetch anomalies to show badge
    const fetchAnomCount = async () => {
      try {
        const res = await api.get('/api/anomaly/summary');
        const critical = Number(res.data?.critical_active || 0);
        const high = Number(res.data?.high_active || 0);
        setAnomalyCount(critical + high);
      } catch (err) { }
    };
    fetchAnomCount();
    const interval = setInterval(fetchAnomCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/auth');
    } catch (err) {
      console.error('Logout failed', err);
    }
  };

  const name = user?.name || 'Authorized User';
  const initial = (user?.name || 'A')[0].toUpperCase();

  return (
    <div className="topbar">
      <div className="tlogo">
        <div className="tlogo-dot"></div>
        Marine<span style={{ color: 'var(--accent)' }}>OS</span>
      </div>
      <div className="tnav">
        <NavLink to="/tracking" className={({ isActive }) => `nbtn ${isActive ? 'on' : ''}`}>⚓ Tracking</NavLink>
        <NavLink to="/twin" className={({ isActive }) => `nbtn ${isActive ? 'on' : ''}`}>🔬 Digital Twin</NavLink>
        <NavLink to="/emissions" className={({ isActive }) => `nbtn ${isActive ? 'on' : ''}`}>🌿 Emissions</NavLink>
        <NavLink to="/anomaly" className={({ isActive }) => `nbtn ${isActive ? 'on' : ''}`}>⚠️ Anomaly</NavLink>
        <NavLink to="/chat" className={({ isActive }) => `nbtn ${isActive ? 'on' : ''}`}>💬 AI Assistant</NavLink>
      </div>
      <div className="tright">
        <div className={`spill ${apiStatus === 'LIVE' ? 'live' : 'err'}`}>
          ● {apiStatus}
        </div>
        {anomalyCount > 0 && <span className="nbadge">{anomalyCount}</span>}
        
        <div className="u-wrap" ref={menuRef}>
          <div className="ubadge" onClick={() => setShowUserMenu(!showUserMenu)} title="Profile Options">
            <div className="uav">{initial}</div>
            <span id="uname">{name}</span>
            <span style={{ fontSize: '10px', marginLeft: '5px', opacity: 0.6 }}>▼</span>
          </div>

          {showUserMenu && (
            <div className="u-dropdown">
              <div className="u-info">
                <span className="u-name">{name}</span>
                <span className="u-email">{user?.email || 'user@example.com'}</span>
              </div>
              
              <button className="u-item" onClick={() => { navigate('/profile'); setShowUserMenu(false); }}>
                <UserIcon size={14} /> Profile Settings
              </button>
              
              <button className="u-item logout" onClick={handleLogout}>
                <LogOut size={14} /> Logout Session
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Topbar;
