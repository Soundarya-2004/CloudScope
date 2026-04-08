import { useState, useEffect } from 'react';
import { fetchWithConfig } from '../api';
import { Save, ShieldAlert } from 'lucide-react';

function Settings() {
  const [key, setKey] = useState('');
  const [secret, setSecret] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [status, setStatus] = useState('');
  const [isConfigured, setIsConfigured] = useState(false);

  useEffect(() => {
    // Load config
    fetchWithConfig('/aws/config')
      .then(res => {
        if (res.is_configured) {
          setIsConfigured(true);
          setKey(res.aws_access_key); // Shows masked
          setRegion(res.aws_region);
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setStatus('Saving...');
    try {
      const res = await fetchWithConfig('/aws/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          aws_access_key: key,
          aws_secret_key: secret,
          aws_region: region
        })
      });
      setIsConfigured(res.is_configured);
      setKey(res.aws_access_key); // Masked
      setSecret(''); // Clear raw secret from state
      setStatus('Saved successfully!');
      setTimeout(() => setStatus(''), 3000);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  };

  return (
    <div style={{maxWidth: '600px', margin: '0 auto'}}>
      <h1>AWS Setup</h1>
      <p style={{color: 'var(--text-secondary)', marginBottom: '32px'}}>
        Configure your AWS IAM credentials. For security, your Secret Key will be immediately encrypted at rest using AES-CBC/Fernet symmetric encryption.
      </p>

      <div className="glass-panel">
        <form onSubmit={handleSave}>
          <div className="form-group">
            <label className="form-label">IAM Access Key ID</label>
            <input 
              type="text" 
              className="form-input" 
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="AKIAIOSFODNN7EXAMPLE"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">IAM Secret Access Key {isConfigured && '(Leave blank to keep existing)'}</label>
            <input 
              type="password" 
              className="form-input" 
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
              required={!isConfigured}
            />
          </div>

          <div className="form-group">
            <label className="form-label">AWS Default Region</label>
            <select 
              className="form-input" 
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
              <option value="us-east-1">US East (N. Virginia)</option>
              <option value="us-east-2">US East (Ohio)</option>
              <option value="us-west-1">US West (N. California)</option>
              <option value="us-west-2">US West (Oregon)</option>
              <option value="eu-west-1">Europe (Ireland)</option>
              <option value="ap-south-1">Asia Pacific (Mumbai)</option>
            </select>
          </div>

          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <button type="submit" className="btn btn-primary">
              <Save size={18} /> Save Configuration
            </button>
            {status && <span style={{color: status.includes('Error') ? 'var(--danger-color)' : 'var(--success-color)'}}>{status}</span>}
          </div>
        </form>

        <div style={{marginTop: '32px', padding: '16px', background: 'rgba(255, 71, 87, 0.1)', borderRadius: '8px', border: '1px solid rgba(255, 71, 87, 0.2)'}}>
          <h4 style={{display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--danger-color)', marginBottom: '8px'}}>
            <ShieldAlert size={18} /> Security Notice
          </h4>
          <p style={{fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5'}}>
            We highly recommend using a dedicated IAM User with explicit permissions limited to <code>ec2:ListInstances</code>, <code>ec2:TerminateInstances</code>, and <code>ce:GetCostAndUsage</code> rather than adding administrator credentials. AWS Root credentials are not permitted programmatically.
          </p>
        </div>
      </div>
    </div>
  );
}

export default Settings;
