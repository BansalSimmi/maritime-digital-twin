import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { AuthProvider, useAuth } from './context/AuthContext';

// Import Pages
import Tracking from './pages/Tracking';
import DigitalTwin from './pages/DigitalTwin';
import Emissions from './pages/Emissions';
import Anomaly from './pages/Anomaly';
import Chat from './pages/Chat';
import Auth from './pages/Auth';
import Profile from './pages/Profile';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div id="auth">
        <div className="spin" style={{ width: '40px', height: '40px' }}></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />;
  }

  return <>{children}</>;
};

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/auth" element={<Auth />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/tracking" />} />
        <Route path="tracking" element={<Tracking />} />
        <Route path="twin" element={<DigitalTwin />} />
        <Route path="emissions" element={<Emissions />} />
        <Route path="anomaly" element={<Anomaly />} />
        <Route path="chat" element={<Chat />} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

function App() {
  return (
    <AuthProvider>
      <Router basename={import.meta.env.BASE_URL}>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}

export default App;
