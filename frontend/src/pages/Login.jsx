import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_URL } from '../api';
import { LogIn, Key, CheckCircle } from 'lucide-react';

function Login({ setToken, setUser }) {
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleDemoLogin = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/api/auth/aws-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          aws_access_key: 'demo@cloudscope.io', 
          aws_secret_key: 'demo-sandbox-key', 
          aws_region: region,
          auth_mode: 'demo'
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Demo login failed');
      }

      const data = await response.json();
      sessionStorage.setItem('token', data.access_token);
      setToken(data.access_token);

      const userRes = await fetch(`${API_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${data.access_token}` }
      });
      const userData = await userRes.json();
      setUser(userData);
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const keyToUse = accessKey.trim();
    const isEmailOrDemo = keyToUse.includes('@') || keyToUse.toLowerCase().includes('demo');
    const secretToUse = secretKey || (isEmailOrDemo ? 'demo-secret-key' : '');

    try {
      const response = await fetch(`${API_URL}/api/auth/aws-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          aws_access_key: keyToUse, 
          aws_secret_key: secretToUse, 
          aws_region: region,
          auth_mode: isEmailOrDemo ? 'demo' : 'explicit'
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Invalid AWS credentials');
      }

      const data = await response.json();
      sessionStorage.setItem('token', data.access_token);
      setToken(data.access_token);

      // fetch user info
      const userRes = await fetch(`${API_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${data.access_token}` }
      });
      const userData = await userRes.json();
      setUser(userData);
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  return (
    <div className="login-container fade-in">
      <div className="glass-panel login-panel" style={{ maxWidth: '480px', width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div className="logo-icon center" style={{ margin: '0 auto' }}>
             <Key size={32} color="#6c5ce7" />
          </div>
          <h2 style={{ marginTop: '0.8rem', color: '#fff' }}>
            CloudScope
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Autonomous AWS Cloud Cost Janitor & Safety Cleanup Agent
          </p>
        </div>

        {error && <div className="error-message" style={{color: 'var(--danger-color)', marginBottom: 16, textAlign: 'center', padding: '10px', background: 'rgba(235, 87, 87, 0.1)', borderRadius: '8px'}}>{error}</div>}

        {/* Quick Launch Demo Sandbox Option */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(108, 92, 231, 0.12), rgba(0, 184, 148, 0.12))',
          border: '1px solid rgba(108, 92, 231, 0.35)',
          borderRadius: '12px',
          padding: '1.25rem',
          marginBottom: '1.5rem',
          textAlign: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '0.85rem', color: '#a29bfe', fontWeight: 700, marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            ⚡ No AWS Account Required
          </div>
          <p style={{ fontSize: '0.82rem', color: '#b2bec3', marginBottom: '1rem', lineHeight: '1.4' }}>
            Test live cloud discovery, one-click component deletion, and TrueFoundry agent auto-termination in real-time.
          </p>
          <button 
            type="button" 
            id="btn-launch-demo-sandbox"
            onClick={handleDemoLogin} 
            className="btn" 
            style={{ 
              width: '100%', 
              padding: '12px', 
              background: 'linear-gradient(135deg, #6c5ce7 0%, #00b894 100%)',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.95rem',
              border: 'none',
              borderRadius: '8px',
              boxShadow: '0 4px 15px rgba(108, 92, 231, 0.35)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}
            disabled={loading}
          >
            {loading ? 'Launching Sandbox...' : <>🚀 Launch Live Demo Sandbox</>}
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', margin: '1.25rem 0', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
          <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.1)' }}></div>
          <span style={{ padding: '0 10px', textTransform: 'uppercase', letterSpacing: '1px' }}>OR CONNECT REAL AWS ACCOUNT</span>
          <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.1)' }}></div>
        </div>
        
        <form onSubmit={handleLogin} className="flex-col" style={{ gap: '1.2rem' }}>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: '0.85rem' }}>AWS Access Key ID or Email</label>
            <input 
              type="text" 
              id="input-aws-access-key"
              value={accessKey}
              onChange={e => setAccessKey(e.target.value)}
              className="premium-input"
              placeholder="AKIAIOSFODNN7EXAMPLE or user@email.com"
              required 
            />
            <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              💡 Entering any email or demo key automatically signs into the Demo Sandbox.
            </small>
          </div>
          
          <div className="form-group">
            <label className="form-label" style={{ fontSize: '0.85rem' }}>AWS Secret Access Key</label>
            <input 
              type="password" 
              id="input-aws-secret-key"
              value={secretKey}
              onChange={e => setSecretKey(e.target.value)}
              className="premium-input"
              placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY (optional for demo)"
            />
          </div>

          <div className="form-group">
            <label className="form-label" style={{ fontSize: '0.85rem' }}>AWS Region</label>
            <select 
              value={region}
              onChange={e => setRegion(e.target.value)}
              className="premium-input"
              style={{ appearance: 'auto', backgroundColor: '#1a1b23' }}
              required 
            >
              <option value="us-east-1">US East (N. Virginia) - us-east-1</option>
              <option value="us-east-2">US East (Ohio) - us-east-2</option>
              <option value="us-west-1">US West (N. California) - us-west-1</option>
              <option value="us-west-2">US West (Oregon) - us-west-2</option>
              <option value="ap-south-1">Asia Pacific (Mumbai) - ap-south-1</option>
              <option value="eu-west-1">Europe (Ireland) - eu-west-1</option>
              <option value="eu-central-1">Europe (Frankfurt) - eu-central-1</option>
            </select>
          </div>

          <button type="submit" id="btn-submit-aws-login" className="btn btn-primary" style={{ width: '100%', padding: '12px', marginTop: '0.5rem' }} disabled={loading}>
            {loading ? 'Authenticating...' : <><LogIn size={16} className="inline mr-1" /> Sign In with AWS Credentials</>}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
