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

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/auth/aws-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          aws_access_key: accessKey, 
          aws_secret_key: secretKey, 
          aws_region: region 
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Invalid AWS credentials');
      }

      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);

      // fetch (dummy) user info so the UI doesn't crash
      const userRes = await fetch(`${API_URL}/auth/me`, {
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
      <div className="glass-panel login-panel">
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div className="logo-icon center">
             <Key size={32} color="#6c5ce7" />
          </div>
          <h2 style={{ marginTop: '1rem', color: '#fff' }}>
            AWS Startup Dashboard
          </h2>
          <p style={{ color: 'var(--text-secondary)' }}>
            Log in directly with your AWS Keys. No account required.
          </p>
        </div>
        
        {error && <div className="error-message" style={{color: 'var(--danger-color)', marginBottom: 16, textAlign: 'center'}}>{error}</div>}
        
        <form onSubmit={handleLogin} className="flex-col" style={{ gap: '1.5rem' }}>
          <div className="form-group">
            <label className="form-label">AWS Access Key ID</label>
            <input 
              type="text" 
              value={accessKey}
              onChange={e => setAccessKey(e.target.value)}
              className="premium-input"
              placeholder="AKIAIOSFODNN7EXAMPLE"
              required 
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">AWS Secret Access Key</label>
            <input 
              type="password" 
              value={secretKey}
              onChange={e => setSecretKey(e.target.value)}
              className="premium-input"
              placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
              required 
            />
          </div>

          <div className="form-group">
            <label className="form-label">AWS Region</label>
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
              <option value="af-south-1">Africa (Cape Town) - af-south-1</option>
              <option value="ap-east-1">Asia Pacific (Hong Kong) - ap-east-1</option>
              <option value="ap-south-1">Asia Pacific (Mumbai) - ap-south-1</option>
              <option value="ap-northeast-3">Asia Pacific (Osaka) - ap-northeast-3</option>
              <option value="ap-northeast-2">Asia Pacific (Seoul) - ap-northeast-2</option>
              <option value="ap-southeast-1">Asia Pacific (Singapore) - ap-southeast-1</option>
              <option value="ap-southeast-2">Asia Pacific (Sydney) - ap-southeast-2</option>
              <option value="ap-northeast-1">Asia Pacific (Tokyo) - ap-northeast-1</option>
              <option value="ca-central-1">Canada (Central) - ca-central-1</option>
              <option value="eu-central-1">Europe (Frankfurt) - eu-central-1</option>
              <option value="eu-west-1">Europe (Ireland) - eu-west-1</option>
              <option value="eu-west-2">Europe (London) - eu-west-2</option>
              <option value="eu-south-1">Europe (Milan) - eu-south-1</option>
              <option value="eu-west-3">Europe (Paris) - eu-west-3</option>
              <option value="eu-north-1">Europe (Stockholm) - eu-north-1</option>
              <option value="me-south-1">Middle East (Bahrain) - me-south-1</option>
              <option value="sa-east-1">South America (São Paulo) - sa-east-1</option>
            </select>
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px' }} disabled={loading}>
            {loading ? 'Authenticating...' : <><LogIn size={16} className="inline mr-1" /> Sign In</>}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
