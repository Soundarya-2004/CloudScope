import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Settings, LogOut, User as UserIcon } from 'lucide-react';

function Sidebar({ user, setToken, setUser }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    navigate('/login');
  };

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">CloudScope</div>
      
      <div style={{ flex: 1 }}>
        <NavLink 
          to="/" 
          className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
        >
          <LayoutDashboard size={20} />
          Infrastructure
        </NavLink>
      </div>

      <div className="sidebar-footer" style={{ borderTop: '1px solid #ffffff15', paddingTop: '16px' }}>
        {user && (
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px', color: 'var(--text-secondary)' }}>
            <UserIcon size={18} style={{ marginRight: '8px' }}/>
            <div style={{ fontSize: '13px' }}>
              <div><strong>{user.username}</strong></div>
              <div style={{ fontSize: '11px', color: '#6c5ce7' }}>{user.role} Role</div>
            </div>
          </div>
        )}
        <button className="btn" onClick={handleLogout} style={{ width: '100%', display: 'flex', justifyContent: 'center', gap: '8px' }}>
          <LogOut size={16} /> Logout
        </button>
      </div>
    </nav>
  );
}

export default Sidebar;
