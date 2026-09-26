import { useState, useEffect } from 'react';
import { 
  CheckSquare, ShieldAlert, CheckCircle, XCircle, Clock, 
  Trash2, Play, AlertCircle, RefreshCw, Server, Box, Zap
} from 'lucide-react';
import { fetchWithConfig } from '../api';

function ApprovalsPage() {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL'); // ALL, PENDING, APPROVED, REJECTED, COMPLETED
  const [executingId, setExecutingId] = useState(null);
  const [executionResult, setExecutionResult] = useState(null);

  const loadApprovals = async () => {
    setLoading(true);
    try {
      const data = await fetchWithConfig('/approvals');
      setApprovals(data || []);
    } catch (err) {
      console.error("Failed to load approvals:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadApprovals();
  }, []);

  const handleApprove = async (id) => {
    try {
      await fetchWithConfig(`/approvals/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Approved via Approvals Gate UI', auto_execute: false })
      });
      loadApprovals();
    } catch (err) {
      alert(`Approval error: ${err.message}`);
    }
  };

  const handleApproveAndTerminate = async (id) => {
    if (!window.confirm("CONFIRMATION: You are granting permission to terminate this cloud resource. The agent will execute termination automatically inside the security sandbox. Proceed?")) {
      return;
    }
    setExecutingId(id);
    setExecutionResult(null);
    try {
      const res = await fetchWithConfig(`/approvals/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Approved with auto-terminate instruction', auto_execute: true })
      });
      setExecutionResult({
        id,
        success: res.execution ? res.execution.success : true,
        message: res.message,
        details: res.execution?.details
      });
      loadApprovals();
    } catch (err) {
      setExecutionResult({ id, success: false, error: err.message });
      loadApprovals();
    }
    setExecutingId(null);
  };

  const handleApproveAllPending = async () => {
    const pending = approvals.filter(a => a.status === 'PENDING');
    if (pending.length === 0) return;
    if (!window.confirm(`CRITICAL: Are you sure you want to approve and automatically terminate all ${pending.length} pending resources?`)) {
      return;
    }
    setLoading(true);
    for (const item of pending) {
      try {
        await fetchWithConfig(`/approvals/${item.id}/approve`, {
          method: 'POST',
          body: JSON.stringify({ reason: 'Batch approved with auto-terminate instruction', auto_execute: true })
        });
      } catch (err) {
        console.error(`Failed to auto-terminate ${item.id}:`, err);
      }
    }
    loadApprovals();
  };

  const handleReject = async (id) => {
    try {
      await fetchWithConfig(`/approvals/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Rejected via Approvals Gate UI' })
      });
      loadApprovals();
    } catch (err) {
      alert(`Rejection error: ${err.message}`);
    }
  };

  const handleExecute = async (id) => {
    if (!window.confirm("CRITICAL CONFIRMATION: Are you sure you want to execute this destructive cloud cleanup inside the sandbox?")) {
      return;
    }
    setExecutingId(id);
    setExecutionResult(null);
    try {
      const res = await fetchWithConfig(`/approvals/${id}/execute`, { method: 'POST' });
      setExecutionResult({ id, success: true, message: res.message, details: res.details });
      loadApprovals();
    } catch (err) {
      setExecutionResult({ id, success: false, error: err.message });
      loadApprovals();
    }
    setExecutingId(null);
  };

  const filtered = approvals.filter(a => {
    if (filter === 'ALL') return true;
    return a.status === filter;
  });

  return (
    <div className="fade-in pb-12">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ margin: 0 }}>Human Approval Gate</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Mandatory checkpoint preventing irreversible cloud actions without explicit authorization
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {approvals.filter(a => a.status === 'PENDING').length > 0 && (
            <button 
              onClick={handleApproveAllPending} 
              className="btn btn-sm btn-danger"
              style={{ background: 'linear-gradient(135deg, #ff4757 0%, #e040fb 100%)', color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Zap size={14} /> Approve & Auto-Terminate All ({approvals.filter(a => a.status === 'PENDING').length})
            </button>
          )}
          <button onClick={loadApprovals} className="btn btn-sm">
            <RefreshCw size={14} className="mr-1" /> Refresh
          </button>
        </div>
      </div>

      {/* Execution Result Banner */}
      {executionResult && (
        <div className="glass-panel animate-fade-in" style={{
          marginBottom: 20, padding: 16,
          background: executionResult.success ? 'rgba(46, 213, 115, 0.15)' : 'rgba(255, 71, 87, 0.15)',
          border: `1px solid ${executionResult.success ? '#2ed573' : '#ff4757'}`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {executionResult.success ? <CheckCircle color="#2ed573" /> : <AlertCircle color="#ff4757" />}
            <div>
              <div style={{ fontWeight: 700, color: '#fff' }}>
                {executionResult.success ? "Sandboxed Execution & Post-Verification Succeeded" : "Sandboxed Execution Blocked or Failed"}
              </div>
              <div style={{ fontSize: 13, color: '#ccc', marginTop: 2 }}>
                {executionResult.message || executionResult.error}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* FILTER TABS */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, borderBottom: '1px solid #ffffff10', paddingBottom: 10 }}>
        {['ALL', 'PENDING', 'APPROVED', 'REJECTED', 'COMPLETED'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              background: filter === f ? '#6c5ce7' : 'transparent',
              color: filter === f ? '#fff' : '#a0a4a8',
              border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12,
              fontWeight: 600, cursor: 'pointer'
            }}
          >
            {f} ({approvals.filter(a => f === 'ALL' || a.status === f).length})
          </button>
        ))}
      </div>

      {/* APPROVAL CARDS */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#a0a4a8' }}>
            <RefreshCw className="animate-spin mb-2" size={28} />
            <div>Loading approval requests...</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass-panel" style={{ textAlign: 'center', padding: 60, color: '#a0a4a8' }}>
            <CheckCircle size={40} color="#2ed573" style={{ margin: '0 auto 12px' }} />
            <div style={{ fontWeight: 700, color: '#fff' }}>No approvals matching filter: {filter}</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>Deploy the agent from the Agent Console to scan for wasteful resources.</div>
          </div>
        ) : (
          filtered.map(req => (
            <div key={req.id} className="glass-panel" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    background: req.risk_level === 'HIGH' ? '#ff475720' : '#f39c1220',
                    border: `1px solid ${req.risk_level === 'HIGH' ? '#ff475740' : '#f39c1240'}`,
                    padding: 10, borderRadius: 8
                  }}>
                    {req.resource_type === 'ec2' && <Server size={22} color="#6c5ce7" />}
                    {req.resource_type === 'ebs' && <Box size={22} color="#f39c12" />}
                    {req.resource_type === 'elb' && <Zap size={22} color="#2ed573" />}
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 800, color: '#fff', fontSize: 16 }}>{req.resource_name}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 700, textTransform: 'uppercase', padding: '2px 6px', borderRadius: 4,
                        background: req.status === 'PENDING' ? '#f39c1225' : (req.status === 'APPROVED' ? '#2ed57325' : '#ff475725'),
                        color: req.status === 'PENDING' ? '#f39c12' : (req.status === 'APPROVED' ? '#2ed573' : '#ff4757')
                      }}>
                        {req.status}
                      </span>
                      <span style={{
                        fontSize: 10, fontWeight: 700, textTransform: 'uppercase', padding: '2px 6px', borderRadius: 4,
                        background: '#ff475715', color: '#ff4757'
                      }}>
                        {req.risk_level} RISK
                      </span>
                    </div>

                    <div style={{ fontFamily: 'monospace', fontSize: 12, color: '#a0a4a8', marginTop: 2 }}>
                      {req.resource_id} • Region: {req.region} • Action: <code style={{ color: '#fff' }}>{req.action}</code>
                    </div>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#2ed573' }}>
                    ${req.estimated_monthly_savings.toFixed(2)}/mo
                  </div>
                  <div style={{ fontSize: 11, color: '#a0a4a8' }}>
                    ${(req.estimated_monthly_savings * 12).toFixed(2)}/yr savings
                  </div>
                </div>
              </div>

              {/* Evidence & Dependencies */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginTop: 16 }}>
                <div style={{ background: 'rgba(0,0,0,0.25)', padding: 12, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#a0a4a8', marginBottom: 6 }}>EVIDENCE SUMMARY:</div>
                  {req.evidence && req.evidence.map((ev, i) => (
                    <div key={i} style={{ fontSize: 12, color: '#ccc', lineHeight: 1.4 }}>• {ev}</div>
                  ))}
                </div>

                <div style={{ background: 'rgba(0,0,0,0.25)', padding: 12, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#a0a4a8', marginBottom: 6 }}>DEPENDENCIES & RISKS:</div>
                  {req.dependencies && req.dependencies.length > 0 ? (
                    req.dependencies.map((dep, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#ff7979', lineHeight: 1.4 }}>⚠ {dep}</div>
                    ))
                  ) : (
                    <div style={{ fontSize: 12, color: '#2ed573' }}>✓ No critical dependencies detected</div>
                  )}
                </div>
              </div>

              {/* Footer controls & security metadata */}
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginTop: 16, paddingTop: 12, borderTop: '1px solid #ffffff0a', flexWrap: 'wrap', gap: 10
              }}>
                <div style={{ fontSize: 11, color: '#777', fontFamily: 'monospace' }}>
                  Plan Hash: {req.plan_hash ? req.plan_hash.substring(0, 16) : 'N/A'}... • Expires: {new Date(req.expires_at).toLocaleTimeString()}
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {req.status === 'PENDING' && (
                    <>
                      <button 
                        onClick={() => handleApproveAndTerminate(req.id)}
                        disabled={executingId === req.id}
                        className="btn btn-sm btn-danger"
                        style={{
                          background: 'linear-gradient(135deg, #ff4757 0%, #e040fb 100%)',
                          color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 6,
                          boxShadow: '0 2px 10px rgba(255, 71, 87, 0.3)'
                        }}
                      >
                        {executingId === req.id ? (
                          <RefreshCw className="animate-spin" size={14} />
                        ) : (
                          <Zap size={14} />
                        )}
                        <span>{executingId === req.id ? "Terminating in AWS..." : "Approve & Terminate Now"}</span>
                      </button>
                      <button 
                        onClick={() => handleApprove(req.id)}
                        className="btn btn-sm"
                        style={{ background: 'rgba(46, 213, 115, 0.2)', color: '#2ed573', border: '1px solid #2ed57350', fontWeight: 600 }}
                      >
                        <CheckCircle size={14} className="mr-1 inline" /> Review Only
                      </button>
                      <button 
                        onClick={() => handleReject(req.id)}
                        className="btn btn-sm"
                        style={{ background: 'rgba(255,255,255,0.05)', color: '#a0a4a8' }}
                      >
                        <XCircle size={14} className="mr-1 inline" /> Reject
                      </button>
                    </>
                  )}

                  {req.status === 'APPROVED' && (
                    <button 
                      onClick={() => handleExecute(req.id)}
                      disabled={executingId === req.id}
                      className="btn btn-sm btn-danger"
                      style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      {executingId === req.id ? (
                        <RefreshCw className="animate-spin" size={14} />
                      ) : (
                        <Play size={14} />
                      )}
                      <span>{executingId === req.id ? "Sandboxed Executing..." : "Execute in Sandbox"}</span>
                    </button>
                  )}

                  {req.status === 'COMPLETED' && (
                    <span style={{ color: '#2ed573', fontSize: 12, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <CheckCircle size={14} /> Executed & Verified in AWS
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default ApprovalsPage;
