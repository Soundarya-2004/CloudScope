import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, Bot, Server, DollarSign, FileText, 
  CheckSquare, Shield, Settings, LogOut, Bell, ShieldAlert,
  Radio
} from 'lucide-react';
import { fetchWithConfig } from '../api';

function Sidebar({ user, setToken, setUser, pendingApprovalsCount = 0 }) {
  const navigate = useNavigate();
  const [identity, setIdentity] = useState(null);

  useEffect(() => {
    fetchWithConfig('/aws/identity')
      .then(data => setIdentity(data))
      .catch(() => {});
  }, []);

  const handleLogout = () => {
    sessionStorage.removeItem('token');
    setToken(null);
    setUser(null);
    navigate('/login');
  };

  return (
    <nav className="sidebar">
      <div className="sidebar-header" style={{ padding: '20px 16px', borderBottom: '1px solid #ffffff10' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            background: 'linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%)',
            padding: 8, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Bot size={22} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, color: '#fff', letterSpacing: 0.5 }}>CloudScope</div>
            <div style={{ fontSize: 11, color: '#6c5ce7', fontWeight: 600 }}>Autonomous Cost Janitor</div>
          </div>
        </div>

        {/* AWS Account Badge */}
        {identity && identity.is_authenticated && (
          <div style={{
            marginTop: 14, padding: '8px 10px', background: '#ffffff08',
            borderRadius: 6, border: '1px solid #ffffff10', fontSize: 11
          }}>
            <div style={{ color: '#a0a4a8', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>AWS Account</span>
              <span style={{
                color: identity.agent_mode === 'ACTION' ? '#ff4757' : '#2ed573',
                fontWeight: 700, fontSize: 10, textTransform: 'uppercase',
                background: identity.agent_mode === 'ACTION' ? '#ff475715' : '#2ed57315',
                padding: '1px 6px', borderRadius: 4
              }}>
                {identity.agent_mode}
              </span>
            </div>
            <div style={{ color: '#fff', fontWeight: 700, marginTop: 2, fontFamily: 'monospace' }}>
              {identity.account_id}
            </div>
            <div style={{ color: '#a0a4a8', fontSize: 10, marginTop: 2 }}>
              {identity.region}
            </div>
          </div>
        )}
      </div>
      
      <div className="nav-links-container" style={{ flex: 1, padding: '16px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        <NavLink to="/agent" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <Bot size={18} />
          <span>Agent Console</span>
          <span style={{
            marginLeft: 'auto', background: '#6c5ce7', color: '#fff',
            fontSize: 10, padding: '2px 6px', borderRadius: 10, fontWeight: 700
          }}>
            LIVE
          </span>
        </NavLink>

        <NavLink to="/resources" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <Server size={18} />
          <span>Resources</span>
        </NavLink>

        <NavLink to="/cost" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <DollarSign size={18} />
          <span>Cost & Waste</span>
        </NavLink>

        <NavLink to="/cleanup-plan" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <FileText size={18} />
          <span>Cleanup Plan</span>
        </NavLink>

        <NavLink to="/approvals" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <CheckSquare size={18} />
          <span>Approvals Gate</span>
          {pendingApprovalsCount > 0 && (
            <span style={{
              marginLeft: 'auto', background: '#ff4757', color: '#fff',
              fontSize: 10, padding: '2px 6px', borderRadius: 10, fontWeight: 800
            }}>
              {pendingApprovalsCount}
            </span>
          )}
        </NavLink>

        <NavLink to="/audit" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <Shield size={18} />
          <span>Audit Trail</span>
        </NavLink>

        <NavLink to="/settings" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          <Settings size={18} />
          <span>Settings</span>
        </NavLink>
      </div>

      <div className="sidebar-footer" style={{ borderTop: '1px solid #ffffff10', padding: '16px' }}>
        <button className="btn" onClick={handleLogout} style={{ width: '100%', display: 'flex', justifyContent: 'center', gap: '8px' }}>
          <LogOut size={16} /> Logout
        </button>
      </div>
    </nav>
  );
}

export default Sidebar;
