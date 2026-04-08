import { useState } from 'react';
import { fetchWithConfig } from '../api';
import { ShieldAlert, Key, CheckCircle, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

function IAMWizard() {
  const [step, setStep] = useState(1);
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await fetchWithConfig('/aws/config', {
        method: 'POST',
        body: JSON.stringify({ aws_access_key: accessKey, aws_secret_key: secretKey, aws_region: region })
      });
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <div className="wizard-container fade-in">
      <div className="glass-panel" style={{ maxWidth: 600, margin: '40px auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '24px' }}>
          <ShieldAlert size={32} color="#f39c12" style={{ marginRight: 16 }} />
          <h2>AWS Setup Wizard</h2>
        </div>

        {step === 1 && (
          <div className="wizard-step animate-fade-in">
            <h3>Step 1: Create an IAM User</h3>
            <p>Do NOT use your AWS Root Account credentials. Follow these steps for least privilege access:</p>
            <ol style={{ lineHeight: '1.8' }}>
              <li>Log in to your AWS Console and go to <strong>IAM</strong>  <strong>Users</strong>.</li>
              <li>Click <strong>Add users</strong> and provide a name (e.g., <code>StartupDashboardApp</code>).</li>
              <li>Attach an inline policy or carefully curated managed policies (e.g., <code>AmazonEC2ReadOnlyAccess</code> plus specific permissions to terminate tagged instances or interact with CE / Cost Explorer).</li>
              <li>Create an <strong>Access Key</strong> for this user (Application type).</li>
            </ol>
            <button className="btn btn-primary" onClick={() => setStep(2)}>
              I have my IAM Keys <ArrowRight size={16} className="inline ml-1" />
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="wizard-step animate-fade-in">
            <h3>Step 2: Enter Credentials</h3>
            {error && <div className="error-message">{error}</div>}
            <div className="form-group">
              <label><Key size={14} className="inline mr-1" /> Access Key ID</label>
              <input type="text" className="premium-input" value={accessKey} onChange={e => setAccessKey(e.target.value)} placeholder="AKIAIOSFODNN7EXAMPLE" />
            </div>
            <div className="form-group">
              <label><Key size={14} className="inline mr-1" /> Secret Access Key</label>
              <input type="password" className="premium-input" value={secretKey} onChange={e => setSecretKey(e.target.value)} placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" />
            </div>
            <div className="form-group">
              <label>Default Region</label>
              <input type="text" className="premium-input" value={region} onChange={e => setRegion(e.target.value)} placeholder="us-east-1" />
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
              <button className="btn" onClick={() => setStep(1)}>Back</button>
              <button className="btn btn-primary flex-1" onClick={handleSave} disabled={saving || !accessKey || !secretKey}>
                {saving ? 'Validating & Saving...' : <><CheckCircle size={16} className="inline mr-1" /> Connect to AWS</>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default IAMWizard;
