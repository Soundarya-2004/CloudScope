import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import AgentControlCenter from './pages/AgentControlCenter';
import ResourcesPage from './pages/ResourcesPage';
import CostPage from './pages/CostPage';
import CleanupPlanPage from './pages/CleanupPlanPage';
import ApprovalsPage from './pages/ApprovalsPage';
import AuditTrailPage from './pages/AuditTrailPage';
import Settings from './pages/Settings';
import Login from './pages/Login';
import { fetchWithConfig } from './api';
import './index.css';

function App() {
  const [token, setToken] = useState(sessionStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);

  useEffect(() => {
    const initApp = async () => {
      if (token) {
        try {
          const userRes = await fetchWithConfig('/auth/me');
          setUser(userRes);
          // Query pending approvals for badge
          try {
            const apps = await fetchWithConfig('/approvals?status_filter=PENDING');
            setPendingApprovalsCount(apps ? apps.length : 0);
          } catch (e) {}
        } catch (err) {
          setToken(null);
          sessionStorage.removeItem('token');
        }
      }
      setLoading(false);
    };
    initApp();
  }, [token]);

  if (loading) return <div className="p-4" style={{ color: '#fff' }}>Initializing CloudScope...</div>;

  const ProtectedRoute = ({ children }) => {
    if (!token) return <Navigate to="/login" />;
    return (
      <div className="app-container">
        <Sidebar 
          user={user} 
          setToken={setToken} 
          setUser={setUser} 
          pendingApprovalsCount={pendingApprovalsCount} 
        />
        <main className="main-content">
          {children}
        </main>
      </div>
    );
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/" /> : <Login setToken={setToken} setUser={setUser} />} />
        <Route path="/" element={<ProtectedRoute><Dashboard user={user} /></ProtectedRoute>} />
        <Route path="/agent" element={<ProtectedRoute><AgentControlCenter user={user} /></ProtectedRoute>} />
        <Route path="/resources" element={<ProtectedRoute><ResourcesPage user={user} /></ProtectedRoute>} />
        <Route path="/cost" element={<ProtectedRoute><CostPage user={user} /></ProtectedRoute>} />
        <Route path="/cleanup-plan" element={<ProtectedRoute><CleanupPlanPage user={user} /></ProtectedRoute>} />
        <Route path="/approvals" element={<ProtectedRoute><ApprovalsPage user={user} /></ProtectedRoute>} />
        <Route path="/audit" element={<ProtectedRoute><AuditTrailPage user={user} /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><Settings user={user} /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
