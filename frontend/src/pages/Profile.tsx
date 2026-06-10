import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Mail, Shield, Bell, Globe, Compass, Activity, LogOut } from 'lucide-react';

const Profile = () => {
  const { user, logout } = useAuth();
  
  // Mock states for profile settings
  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [units, setUnits] = useState<'KNOTS' | 'KMH'>('KNOTS');
  const [timezone, setTimezone] = useState<'UTC' | 'LOCAL'>('UTC');
  const [notifications, setNotifications] = useState(true);

  const initial = (user?.name || 'A')[0].toUpperCase();

  return (
    <div className="page" style={{ 
      background: "url('/assets/auth_bg.png') no-repeat center center / cover", 
      minHeight: '100%', 
      display: 'flex', 
      alignItems: 'flex-start', 
      justifyContent: 'center',
      paddingTop: '80px',
      position: 'relative'
    }}>
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'rgba(2, 11, 20, 0.85)',
        zIndex: 1
      }}></div>

      <div className="acard" style={{ padding: '40px', width: '600px', zIndex: 10, position: 'relative' }}>
        <div className="alogo" style={{ marginBottom: '32px' }}>
          <div className="alogo-icon"><User size={24} color="var(--accent)" /></div>
          <div className="alogo-name">Commander Profile</div>
          <div className="alogo-sub">SYSTEM CLEARANCE: {user?.role?.toUpperCase() || 'USER'}</div>
        </div>

        <div className="aform" style={{ gap: '24px' }}>
          {/* Identity Section */}
          <div className="a-subtitle" style={{ textAlign: 'left', marginBottom: '8px' }}>Personal Identity</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="aform-group">
              <div className="aform-icon"><User size={18} /></div>
              <div className="aform-inner">
                <label>Full Name</label>
                <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            </div>
            <div className="aform-group">
              <div className="aform-icon"><Mail size={18} /></div>
              <div className="aform-inner">
                <label>Email Address</label>
                <input type="email" value={email} readOnly />
              </div>
            </div>
          </div>

          {/* Operational Preferences */}
          <div className="a-subtitle" style={{ textAlign: 'left', marginBottom: '8px', marginTop: '16px' }}>Operational Preferences</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="aform-group" style={{ cursor: 'pointer' }} onClick={() => setUnits(units === 'KNOTS' ? 'KMH' : 'KNOTS')}>
              <div className="aform-icon"><Compass size={18} /></div>
              <div className="aform-inner">
                <label>Navigation Units</label>
                <div style={{ color: '#fff', fontSize: '15px', fontWeight: 600 }}>{units === 'KNOTS' ? 'Nautical Miles / Knots' : 'Kilometers / KMH'}</div>
              </div>
            </div>
            <div className="aform-group" style={{ cursor: 'pointer' }} onClick={() => setTimezone(timezone === 'UTC' ? 'LOCAL' : 'UTC')}>
              <div className="aform-icon"><Globe size={18} /></div>
              <div className="aform-inner">
                <label>Timezone Sync</label>
                <div style={{ color: '#fff', fontSize: '15px', fontWeight: 600 }}>{timezone === 'UTC' ? 'Global Standard (UTC)' : 'Local System Time'}</div>
              </div>
            </div>
          </div>

          {/* System Settings */}
          <div className="a-subtitle" style={{ textAlign: 'left', marginBottom: '8px', marginTop: '16px' }}>System Connectivity</div>
          <div className="aform-group" style={{ cursor: 'pointer' }} onClick={() => setNotifications(!notifications)}>
            <div className="aform-icon"><Bell size={18} /></div>
            <div className="aform-inner">
              <label>Critical Alerts</label>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ color: '#fff', fontSize: '15px', fontWeight: 600 }}>Real-time Browser Push Notifications</div>
                <div className={`atoggle ${notifications ? 'on' : ''}`}>
                  <div className="atoggle-ball"></div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '24px', display: 'flex', gap: '16px' }}>
            <button className="abtn" style={{ flex: 1 }}>Apply Changes</button>
            <button className="abtn" style={{ flex: 1, background: 'rgba(255, 59, 59, 0.1)', color: 'var(--danger)', boxShadow: 'none' }} onClick={logout}>
              Terminate Session
            </button>
          </div>
        </div>

        <div className="asso-wrap" style={{ marginTop: '32px' }}>
          <div className="asso-text">Recent Activity Logs</div>
          <div style={{ background: 'rgba(8, 22, 42, 0.5)', borderRadius: '12px', padding: '16px', textAlign: 'left', fontStyle: 'italic', fontSize: '12px', color: 'var(--t3)' }}>
            <div style={{ marginBottom: '4px' }}><span style={{ color: 'var(--accent)' }}>[08:45]</span> Session established via secure cookie</div>
            <div style={{ marginBottom: '4px' }}><span style={{ color: 'var(--accent)' }}>[09:12]</span> Vessel Tracking data synchronized</div>
            <div><span style={{ color: 'var(--accent)' }}>[NOW]</span> Profile settings accessed</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;
