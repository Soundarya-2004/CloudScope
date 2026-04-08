import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import { fetchWithConfig } from './api';
import './index.css';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initApp = async () => {
      if (token) {
        try {
          const userRes = await fetchWithConfig('/auth/me');
          setUser(userRes);
        } catch (err) {
          setToken(null);
          localStorage.removeItem('token');
        }
      }
      setLoading(false);
    };
    initApp();
  }, [token]);

  if (loading) return <div className="p-4" style={{color: '#fff'}}>Loading Dashboard...</div>;

  const ProtectedRoute = ({ children }) => {
    if (!token) return <Navigate to="/login" />;
    return (
      <div className="app-container">
        <Sidebar user={user} setToken={setToken} setUser={setUser} />
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
      </Routes>
    </BrowserRouter>
  );
}

export default App;
