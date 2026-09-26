import { useState, useEffect } from 'react';
import { Shield, ShieldAlert, Key, CheckCircle, AlertTriangle, RefreshCw, Lock, Unlock } from 'lucide-react';
import { fetchWithConfig } from '../api';

function Settings() {
  const [identity, setIdentity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [agentMode, setAgentMode] = useState('READ_ONLY');
  const [confirmAction, setConfirmAction] = useState(false);
  const [modeStatus, setModeStatus] = useState('');

  const loadIdentity = async () => {
    setLoading(true);
    try {
      const data = await fetchWithConfig('/aws/identity');
      setIdentity(data);
      if (data) setAgentMode(data.agent_mode || 'READ_ONLY');
    } catch (err) {
      console.error("Failed to load AWS identity:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadIdentity();
  }, []);

  const handleModeChange = async (newMode) => {
    if (newMode === 'ACTION' && !confirmAction) {
      alert("Please check the confirmation box before enabling ACTION mode.");
      return;
    }

    setModeStatus('Updating mode...');
    try {
      await fetchWithConfig('/aws/mode', {
        method: 'POST',
        body: JSON.stringify({ mode: newMode, confirmation: confirmAction })
      });
      setAgentMode(newMode);
      setModeStatus(`Agent mode successfully set to ${newMode}`);
      loadIdentity();
      setTimeout(() => setModeStatus(''), 3000);
    } catch (err) {
      setModeStatus(`Failed to update mode: ${err.message}`);
    }
  };

  return (
    <div className="fade-in pb-12" style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0 }}>System Settings & Governance</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Configure AWS connectivity, permissions validation, and safety execution modes
          </p>
        </div>
        <button onClick={loadIdentity} className="btn btn-sm">
          <RefreshCw size={14} className="mr-1" /> Re-check Identity
        </button>
      </div>

      {/* AGENT MODE SWITCH */}
      <div className="glass-panel" style={{ marginBottom: 24, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          {agentMode === 'ACTION' ? <Unlock size={22} color="#ff4757" /> : <Lock size={22} color="#2ed573" />}
          <h2 style={{ margin: 0, fontSize: 18 }}>Agent Operating Mode</h2>
        </div>

        <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
          By default, CloudScope operates in <strong>READ-ONLY mode</strong>. In this mode, the agent discovers infrastructure,
          reasons over waste, and generates teardown plans, but is strictly barred from executing any destructive actions.
        </p>

        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16, marginBottom: 16
        }}>
          <div 
            onClick={() => handleModeChange('READ_ONLY')}
            style={{
              padding: 16, borderRadius: 8, cursor: 'pointer',
              background: agentMode === 'READ_ONLY' ? 'rgba(46, 213, 115, 0.15)' : 'rgba(255,255,255,0.03)',
              border: `2px solid ${agentMode === 'READ_ONLY' ? '#2ed573' : 'rgba(255,255,255,0.08)'}`
            }}
          >
            <div style={{ fontWeight: 800, color: '#2ed573', fontSize: 14 }}>READ-ONLY MODE (Recommended)</div>
            <div style={{ fontSize: 12, color: '#a0a4a8', marginTop: 4 }}>
              Discovers, analyzes, calculates costs, generates plans. All destructive execution commands are disabled.
            </div>
          </div>

          <div 
            style={{
              padding: 16, borderRadius: 8,
              background: agentMode === 'ACTION' ? 'rgba(255, 71, 87, 0.15)' : 'rgba(255,255,255,0.03)',
              border: `2px solid ${agentMode === 'ACTION' ? '#ff4757' : 'rgba(255,255,255,0.08)'}`
            }}
          >
            <div style={{ fontWeight: 800, color: '#ff4757', fontSize: 14 }}>ACTION MODE</div>
            <div style={{ fontSize: 12, color: '#a0a4a8', marginTop: 4 }}>
              Allows executing approved destructive actions through the sandboxed runner after explicit human authorization.
            </div>
            {agentMode !== 'ACTION' && (
              <div style={{ marginTop: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#ccc', cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={confirmAction} 
                    onChange={e => setConfirmAction(e.target.checked)} 
                    style={{ accentColor: '#ff4757' }}
                  />
                  <span>I authorize sandboxed action execution</span>
                </label>
                <button 
                  onClick={() => handleModeChange('ACTION')}
                  disabled={!confirmAction}
                  className="btn btn-sm btn-danger"
                  style={{ marginTop: 8, width: '100%', padding: '6px 12px' }}
                >
                  Enable Action Mode
                </button>
              </div>
            )}
          </div>
        </div>

        {modeStatus && (
          <div style={{ fontSize: 12, color: modeStatus.includes('Failed') ? '#ff4757' : '#2ed573' }}>
            {modeStatus}
          </div>
        )}
      </div>

      {/* LIVE AWS IDENTITY */}
      <div className="glass-panel" style={{ marginBottom: 24, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <Shield size={22} color="#6c5ce7" />
          <h2 style={{ margin: 0, fontSize: 18 }}>AWS Authentication & STS Identity</h2>
        </div>

        {loading ? (
          <div style={{ padding: 20, textAlign: 'center', color: '#a0a4a8' }}>
            <RefreshCw className="animate-spin mb-2" size={20} />
            <div>Checking STS Caller Identity...</div>
          </div>
        ) : identity && identity.is_authenticated ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #ffffff0a' }}>
              <span style={{ color: '#a0a4a8', fontSize: 13 }}>AWS Account ID:</span>
              <strong style={{ color: '#fff', fontFamily: 'monospace' }}>{identity.account_id}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #ffffff0a' }}>
              <span style={{ color: '#a0a4a8', fontSize: 13 }}>Caller ARN:</span>
              <strong style={{ color: '#fff', fontFamily: 'monospace', fontSize: 12 }}>{identity.arn}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #ffffff0a' }}>
              <span style={{ color: '#a0a4a8', fontSize: 13 }}>Region:</span>
              <strong style={{ color: '#fff' }}>{identity.region}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #ffffff0a' }}>
              <span style={{ color: '#a0a4a8', fontSize: 13 }}>Credential Resolution:</span>
              <span style={{ color: '#6c5ce7', fontWeight: 600 }}>{identity.auth_mode}</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span style={{ color: '#a0a4a8', fontSize: 13 }}>Read Permissions:</span>
              <span style={{ color: identity.read_permissions_valid ? '#2ed573' : '#ff4757', fontWeight: 700 }}>
                {identity.read_permissions_valid ? 'VERIFIED' : 'LIMITED'}
              </span>
            </div>

            {identity.warning && (
              <div style={{
                marginTop: 10, padding: 12, background: 'rgba(243, 156, 18, 0.1)',
                border: '1px solid rgba(243, 156, 18, 0.3)', borderRadius: 6, fontSize: 12, color: '#f39c12'
              }}>
                ⚠ {identity.warning}
              </div>
            )}
          </div>
        ) : (
          <div style={{
            padding: 16, background: 'rgba(255, 71, 87, 0.1)',
            border: '1px solid rgba(255, 71, 87, 0.3)', borderRadius: 8, color: '#ff4757'
          }}>
            <div style={{ fontWeight: 700 }}>AWS Not Connected</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              {identity?.warning || "No valid AWS credentials resolved from IAM Role, Environment, or Profile."}
            </div>
          </div>
        )}
      </div>

      {/* TRUEFORGE INTEGRATION INFO */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <h2 style={{ margin: '0 0 12px 0', fontSize: 18 }}>TrueForge Harness Integration</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
          CloudScope is orchestrating as a vendor-neutral autonomous agent via TrueForge.
          The agent loop bridges model calls (Polaris AI Gateway: <code>vm-polaris/openai</code>),
          Model Context Protocol (MCP) tools for AWS discovery and sandboxed execution,
          and a Human-in-the-Loop governance gate.
        </p>

        <div style={{ marginTop: 12, fontFamily: 'monospace', fontSize: 12, background: 'rgba(0,0,0,0.3)', padding: 12, borderRadius: 6, color: '#a29bfe' }}>
          Config: trueforge.yaml • Gateway: https://gateway.truefoundry.ai • Model: vm-polaris/openai
        </div>
      </div>
    </div>
  );
}

export default Settings;
