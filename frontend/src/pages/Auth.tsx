import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api';
import { User, Lock, Ship } from 'lucide-react';

const Auth = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('user');
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    return <Navigate to="/tracking" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
        navigate('/tracking');
      } else {
        await api.post('/api/users/signup', { name, email, password, role });
        await login(email, password);
        navigate('/tracking');
      }
    } catch (err: any) {
      console.error('Auth Error:', err);
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail[0]?.msg || 'Validation failed');
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError(err.response?.data?.message || 'Authentication failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div id="auth">
      <div className="acard">
        <div className="alogo">
          <div className="alogo-icon">
            <Ship size={24} color="var(--accent)" />
          </div>
          <div className="alogo-name">Maritime Digital Twin</div>
          <div className="alogo-sub">GLOBAL NAVIGATOR</div>
        </div>

        <div className="a-title">System Access</div>
        <div className="a-subtitle">Secure Login to your Virtual Fleet</div>

        <div className="atabs">
          <button 
            className={`atab ${isLogin ? 'on' : ''}`} 
            onClick={() => setIsLogin(true)}
          >
            LOGIN
          </button>
          <button 
            className={`atab ${!isLogin ? 'on' : ''}`} 
            onClick={() => setIsLogin(false)}
          >
            REGISTER
          </button>
        </div>

        <form className="aform" onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="aform-group">
              <div className="aform-icon"><User size={18} /></div>
              <div className="aform-inner">
                <label>Full Name</label>
                <input 
                  type="text" 
                  placeholder="John Doe" 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required 
                />
              </div>
            </div>
          )}

          <div className="aform-group">
            <div className="aform-icon"><User size={18} /></div>
            <div className="aform-inner">
              <label>Username or Email</label>
              <input 
                type="email" 
                placeholder="john.doe@maritime-group.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required 
              />
            </div>
          </div>

          <div className="aform-group">
            <div className="aform-icon"><Lock size={18} /></div>
            <div className="aform-inner">
              <label>Password</label>
              <input 
                type="password" 
                placeholder="••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required 
              />
            </div>
          </div>

          {isLogin && (
            <div className="aform-extras">
              <div className="atoggle-wrap" onClick={() => setRememberMe(!rememberMe)}>
                <div className={`atoggle ${rememberMe ? 'on' : ''}`}>
                  <div className="atoggle-ball"></div>
                </div>
                <span>Keep me logged in</span>
              </div>

            </div>
          )}

          {error && <div className="err-box">{error}</div>}

          <button className="abtn" type="submit" disabled={loading}>
            {loading ? <span className="spin"></span> : (isLogin ? 'Login' : 'Create Account')}
          </button>
        </form>


      </div>
    </div>
  );
};

export default Auth;
