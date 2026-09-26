import { useState, useEffect } from 'react';
import { 
  Server, Box, Zap, DollarSign, TrendingDown, ShieldAlert, 
  CheckCircle, RefreshCw, ArrowRight, Bot, AlertTriangle, Clock,
  Trash2, X, AlertCircle, Sparkles, HardDrive, Cpu, Database, Radio, Cloud
} from 'lucide-react';
import { fetchWithConfig } from '../api';

function Dashboard({ user }) {
  const [identity, setIdentity] = useState(null);
  const [costSummary, setCostSummary] = useState(null);
  const [latestPlan, setLatestPlan] = useState(null);
  const [latestRun, setLatestRun] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [runningResources, setRunningResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanningLive, setScanningLive] = useState(false);

  // Direct Deletion Modal State
  const [selectedForDelete, setSelectedForDelete] = useState(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteResult, setDeleteResult] = useState(null);

  const loadDashboardData = async (forceScan = false) => {
    if (forceScan) setScanningLive(true);
    else setLoading(true);

    try {
      const [idData, costData, planData, runsData, appsData, resData] = await Promise.allSettled([
        fetchWithConfig('/aws/identity'),
        fetchWithConfig('/cost/summary'),
        fetchWithConfig('/plans/latest'),
        fetchWithConfig('/agent/runs'),
        fetchWithConfig('/approvals?status_filter=PENDING'),
        fetchWithConfig(forceScan ? '/resources/scan' : '/resources', { method: forceScan ? 'POST' : 'GET' })
      ]);

      if (idData.status === 'fulfilled') setIdentity(idData.value);
      if (costData.status === 'fulfilled') setCostSummary(costData.value);
      if (planData.status === 'fulfilled') setLatestPlan(planData.value);
      if (runsData.status === 'fulfilled' && runsData.value.length > 0) setLatestRun(runsData.value[0]);
      if (appsData.status === 'fulfilled') setApprovals(appsData.value || []);
      
      if (resData.status === 'fulfilled') {
        const val = resData.value;
        if (forceScan && val.resources) {
          setRunningResources(val.resources);
        } else {
          setRunningResources(Array.isArray(val) ? val : []);
        }
      }
    } catch (err) {
      console.error("Dashboard data load error:", err);
    }
    setLoading(false);
    setScanningLive(false);
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleApproveAllPending = async () => {
    if (approvals.length === 0) return;
    if (!window.confirm(`CRITICAL: Are you sure you want to approve and automatically terminate all ${approvals.length} pending resources?`)) {
      return;
    }
    setLoading(true);
    for (const item of approvals) {
      try {
        await fetchWithConfig(`/approvals/${item.id}/approve`, {
          method: 'POST',
          body: JSON.stringify({ reason: 'Approved & Auto-Terminated from Dashboard', auto_execute: true })
        });
      } catch (err) {
        console.error(`Auto-terminate error for ${item.id}:`, err);
      }
    }
    loadDashboardData();
  };

  const handleConfirmDelete = async () => {
    if (!selectedForDelete || !deleteConfirmed) return;
    setDeleting(true);
    setDeleteResult(null);
    try {
      const res = await fetchWithConfig(`/resources/${selectedForDelete.resource_id}/delete`, {
        method: 'POST',
        body: JSON.stringify({
          resource_type: selectedForDelete.resource_type,
          region: selectedForDelete.region,
          confirmation: true,
          reason: 'User directly terminated component via CloudScope Dashboard'
        })
      });
      setDeleteResult({
        success: true,
        message: res.message || 'Component successfully terminated and verified in AWS.'
      });
      loadDashboardData();
    } catch (err) {
      setDeleteResult({
        success: false,
        error: err.message || 'Failed to terminate component.'
      });
    }
    setDeleting(false);
  };

  const renderServiceIcon = (type) => {
    switch (type.toLowerCase()) {
      case 'ec2': return <Server size={16} color="#6c5ce7" />;
      case 'ebs': return <Box size={16} color="#f39c12" />;
      case 'elb': return <Zap size={16} color="#2ed573" />;
      case 'eip': return <Radio size={16} color="#00cec9" />;
      case 'rds': return <Database size={16} color="#e84393" />;
      case 's3': return <HardDrive size={16} color="#0984e3" />;
      case 'lambda': return <Cpu size={16} color="#fdcb6e" />;
      default: return <Cloud size={16} color="#a29bfe" />;
    }
  };

  const pendingCount = approvals.length;

  return (
    <div className="fade-in pb-12">
      {/* HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>CloudScope Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Autonomous Cloud Cost Janitor — Live Account Oversight, Waste Remediation & Component Deletion
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button 
            onClick={() => loadDashboardData(true)} 
            disabled={scanningLive}
            className="btn btn-primary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            {scanningLive ? <RefreshCw className="animate-spin" size={14} /> : <Sparkles size={14} />}
            <span>{scanningLive ? "Scanning Live..." : "Scan AWS Infrastructure"}</span>
          </button>
          <button onClick={() => loadDashboardData(false)} className="btn btn-sm">
            <RefreshCw size={14} className="mr-1" /> Sync
          </button>
          <a href="/agent" className="btn btn-primary btn-sm" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Bot size={14} /> Open Agent Console
          </a>
        </div>
      </div>

      {/* HUMAN APPROVAL BANNER IF PENDING */}
      {pendingCount > 0 && (
        <div className="glass-panel animate-fade-in" style={{
          marginBottom: 24, padding: 20,
          background: 'linear-gradient(135deg, rgba(243, 156, 18, 0.15) 0%, rgba(231, 76, 60, 0.15) 100%)',
          border: '1px solid rgba(243, 156, 18, 0.4)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ShieldAlert size={28} color="#f39c12" />
              <div>
                <div style={{ fontWeight: 800, color: '#f39c12', fontSize: 16 }}>
                  {pendingCount} DESTRUCTIVE ACTIONS REQUIRE HUMAN APPROVAL
                </div>
                <div style={{ fontSize: 13, color: '#e0e0e0', marginTop: 2 }}>
                  The agent identified wasteful resources and paused at the approval gate. Potential savings: 
                  <strong style={{ color: '#2ed573' }}> ${latestPlan?.total_monthly_savings?.toFixed(2) || '0.00'}/mo</strong>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button 
                onClick={handleApproveAllPending}
                className="btn btn-sm btn-danger"
                style={{
                  background: 'linear-gradient(135deg, #ff4757 0%, #e040fb 100%)',
                  color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px'
                }}
              >
                <Zap size={14} /> Approve & Auto-Terminate All ({pendingCount})
              </button>
              <a href="/approvals" className="btn btn-primary" style={{ padding: '8px 18px', textDecoration: 'none' }}>
                Review Approvals <ArrowRight size={14} className="inline ml-1" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* TOP STAT CARDS */}
      <div className="dashboard-grid" style={{ marginBottom: 24 }}>
        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>AWS Account</h3>
          <div className="stat-value" style={{ fontSize: 20, fontFamily: 'monospace' }}>
            {identity?.account_id || 'Connecting...'}
          </div>
          <div style={{ fontSize: 11, color: '#a0a4a8', marginTop: 4 }}>
            {identity?.region || 'us-east-1'} • Mode: <span style={{ color: identity?.agent_mode === 'ACTION' ? '#ff4757' : '#2ed573', fontWeight: 700 }}>{identity?.agent_mode}</span>
          </div>
        </div>

        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>
            <DollarSign size={16} className="inline mr-1" /> Monthly Spend
          </h3>
          <div className="stat-value">
            ${costSummary?.total_monthly_spend?.toFixed(2) || '0.00'}
          </div>
          <div style={{ fontSize: 11, color: '#a0a4a8', marginTop: 4 }}>
            Live Cost Explorer Data
          </div>
        </div>

        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>
            <TrendingDown size={16} className="inline mr-1" /> Monthly Savings
          </h3>
          <div className="stat-value" style={{ color: '#2ed573' }}>
            ${costSummary?.potential_monthly_savings?.toFixed(2) || '0.00'}
          </div>
          <div style={{ fontSize: 11, color: '#2ed573', marginTop: 4 }}>
            ${costSummary?.potential_annual_savings?.toFixed(2) || '0.00'}/yr annualized
          </div>
        </div>

        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>
            <Server size={16} className="inline mr-1" /> Resources Scanned
          </h3>
          <div className="stat-value">
            {runningResources.length || latestRun?.total_resources_scanned || 0}
          </div>
          <div style={{ fontSize: 11, color: '#f39c12', marginTop: 4 }}>
            {runningResources.filter(r => r.is_waste).length || latestRun?.waste_candidates_count || 0} waste candidates found
          </div>
        </div>
      </div>

      {/* LIVE RUNNING AWS COMPONENTS SECTION */}
      <div className="glass-panel" style={{ marginBottom: 24, padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Server size={18} color="#6c5ce7" /> Live Running AWS Components ({runningResources.length})
            </h3>
            <div style={{ fontSize: 12, color: '#a0a4a8', marginTop: 2 }}>
              Inspect all components running in your AWS account and delete any wasteful resources directly
            </div>
          </div>

          <a href="/resources" style={{ color: '#6c5ce7', fontSize: 12, textDecoration: 'none', fontWeight: 600 }}>
            View Full Inventory →
          </a>
        </div>

        {/* Running Resources Table */}
        <div className="table-container" style={{ maxHeight: 380, overflowY: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Component Name & ID</th>
                <th>Service Type</th>
                <th>State</th>
                <th>Monthly Cost</th>
                <th>Status / Waste Finding</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading || scanningLive ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: 30, color: '#a0a4a8' }}>
                    <RefreshCw className="animate-spin mb-2" size={20} />
                    <div>Scanning live AWS account infrastructure...</div>
                  </td>
                </tr>
              ) : runningResources.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: 30, color: '#a0a4a8' }}>
                    No running components detected. Click "Scan AWS Infrastructure" to inspect account.
                  </td>
                </tr>
              ) : (
                runningResources.slice(0, 8).map(r => (
                  <tr key={r.resource_id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {renderServiceIcon(r.resource_type)}
                        <div>
                          <div style={{ fontWeight: 700, color: '#fff', fontSize: 13 }}>{r.name}</div>
                          <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a4a8', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {r.resource_id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <code style={{ fontSize: 11, textTransform: 'uppercase' }}>{r.resource_type}</code>
                    </td>
                    <td>
                      <span className={`status-badge status-${['running', 'available', 'active'].includes(r.state?.toLowerCase()) ? 'running' : 'stopped'}`}>
                        {r.state}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: r.is_waste ? '#2ed573' : '#fff' }}>
                      ${r.monthly_cost ? r.monthly_cost.toFixed(2) : '0.00'}/mo
                    </td>
                    <td>
                      {r.is_waste ? (
                        <span style={{
                          background: '#ff475720', color: '#ff4757', padding: '3px 8px', borderRadius: 4,
                          fontSize: 11, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4
                        }}>
                          <AlertTriangle size={12} /> {r.waste_finding}
                        </span>
                      ) : (
                        <span style={{ color: '#2ed573', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <CheckCircle size={12} /> In Use / Retained
                        </span>
                      )}
                    </td>
                    <td>
                      {r.state?.toLowerCase() === 'terminated' || r.state?.toLowerCase() === 'deleted' ? (
                        <span style={{ color: '#777', fontSize: 11, fontStyle: 'italic' }}>Terminated</span>
                      ) : (
                        <button
                          onClick={() => {
                            setSelectedForDelete(r);
                            setDeleteConfirmed(false);
                            setDeleteResult(null);
                          }}
                          className="btn btn-sm btn-danger"
                          style={{
                            padding: '4px 10px', fontSize: 11, fontWeight: 700,
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                            background: '#ff475718', border: '1px solid #ff475750', color: '#ff4757'
                          }}
                          title="Terminate / Delete this component"
                        >
                          <Trash2 size={12} /> Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* QUICK AGENT LAUNCH & CANDIDATES OVERVIEW */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24 }}>
        {/* LATEST CLEANUP CANDIDATES */}
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>Active Cleanup Plan Candidates</h3>
            <a href="/cleanup-plan" style={{ color: '#6c5ce7', fontSize: 12, textDecoration: 'none', fontWeight: 600 }}>
              View Full Plan →
            </a>
          </div>

          {!latestPlan || !latestPlan.candidates || latestPlan.candidates.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#a0a4a8' }}>
              <CheckCircle size={32} color="#2ed573" style={{ margin: '0 auto 8px' }} />
              <div>No active waste candidates in the current plan.</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Trigger a scan from the Agent Console to inspect your account.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {latestPlan.candidates.slice(0, 5).map(c => (
                <div key={c.resource_id} style={{
                  padding: 12, background: 'rgba(255,255,255,0.02)', borderRadius: 6,
                  border: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                }}>
                  <div>
                    <div style={{ fontWeight: 700, color: '#fff', fontSize: 13 }}>{c.name}</div>
                    <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a4a8' }}>
                      {c.resource_type.toUpperCase()} • {c.resource_id}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: '#2ed573', fontWeight: 700, fontSize: 14 }}>
                      ${c.monthly_cost.toFixed(2)}/mo
                    </div>
                    <div style={{ fontSize: 10, color: '#f39c12' }}>{c.waste_finding}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AGENT DISPATCH PROMPT CARD */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <Bot size={24} color="#6c5ce7" />
              <h3 style={{ margin: 0, fontSize: 16 }}>Deploy Cloud Cost Janitor</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
              The agent autonomously connects to live AWS APIs, identifies idle compute, unattached storage,
              and orphaned balancers, calculates waste, and stops for human approval.
            </p>
            <div style={{
              background: 'rgba(0,0,0,0.3)', padding: 12, borderRadius: 6,
              fontSize: 12, color: '#a0a4a8', marginTop: 12, fontFamily: 'monospace'
            }}>
              "Find the AWS resources that are costing me money but appear unused."
            </div>
          </div>

          <div style={{ marginTop: 20 }}>
            <a href="/agent" className="btn btn-primary" style={{ width: '100%', textAlign: 'center', textDecoration: 'none', padding: '12px 0' }}>
              Launch in Agent Control Center <ArrowRight size={16} className="inline ml-1" />
            </a>
          </div>
        </div>
      </div>

      {/* DIRECT COMPONENT TERMINATION MODAL */}
      {selectedForDelete && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, padding: 20
        }}>
          <div className="glass-panel animate-fade-in" style={{
            maxWidth: 540, width: '100%', padding: 28,
            border: '1px solid rgba(255, 71, 87, 0.4)',
            boxShadow: '0 20px 50px rgba(0,0,0,0.8)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ background: '#ff475720', border: '1px solid #ff475750', padding: 10, borderRadius: 10 }}>
                  <ShieldAlert size={28} color="#ff4757" />
                </div>
                <div>
                  <h3 style={{ margin: 0, color: '#fff', fontSize: 18 }}>Confirm Component Deletion</h3>
                  <div style={{ color: '#a0a4a8', fontSize: 12, marginTop: 2 }}>
                    Safe destructive termination via isolated sandbox
                  </div>
                </div>
              </div>
              <button 
                onClick={() => setSelectedForDelete(null)}
                style={{ background: 'transparent', border: 'none', color: '#a0a4a8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Component Summary Card */}
            <div style={{ background: 'rgba(0,0,0,0.4)', borderRadius: 8, padding: 16, marginBottom: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
                <div>
                  <span style={{ color: '#a0a4a8', fontSize: 11 }}>RESOURCE NAME:</span>
                  <div style={{ fontWeight: 700, color: '#fff' }}>{selectedForDelete.name}</div>
                </div>
                <div>
                  <span style={{ color: '#a0a4a8', fontSize: 11 }}>SERVICE TYPE:</span>
                  <div style={{ fontWeight: 700, color: '#6c5ce7', textTransform: 'uppercase' }}>
                    {selectedForDelete.resource_type}
                  </div>
                </div>
                <div>
                  <span style={{ color: '#a0a4a8', fontSize: 11 }}>RESOURCE ID:</span>
                  <div style={{ fontFamily: 'monospace', fontSize: 12, color: '#e0e0e0', wordBreak: 'break-all' }}>
                    {selectedForDelete.resource_id}
                  </div>
                </div>
                <div>
                  <span style={{ color: '#a0a4a8', fontSize: 11 }}>MONTHLY COST:</span>
                  <div style={{ fontWeight: 700, color: '#2ed573' }}>
                    ${selectedForDelete.monthly_cost ? selectedForDelete.monthly_cost.toFixed(2) : '0.00'}/mo
                  </div>
                </div>
              </div>
            </div>

            {/* Execution Result Feedback */}
            {deleteResult && (
              <div style={{
                padding: 14, borderRadius: 8, marginBottom: 20,
                background: deleteResult.success ? 'rgba(46, 213, 115, 0.15)' : 'rgba(255, 71, 87, 0.15)',
                border: `1px solid ${deleteResult.success ? '#2ed573' : '#ff4757'}`,
                display: 'flex', alignItems: 'center', gap: 10
              }}>
                {deleteResult.success ? <CheckCircle color="#2ed573" size={20} /> : <AlertCircle color="#ff4757" size={20} />}
                <div>
                  <div style={{ fontWeight: 700, color: '#fff', fontSize: 13 }}>
                    {deleteResult.success ? "Resource Successfully Terminated" : "Termination Blocked or Failed"}
                  </div>
                  <div style={{ fontSize: 12, color: '#ccc', marginTop: 2 }}>
                    {deleteResult.message || deleteResult.error}
                  </div>
                </div>
              </div>
            )}

            {!deleteResult?.success && (
              <>
                <div style={{
                  background: 'rgba(255, 71, 87, 0.08)', border: '1px solid rgba(255, 71, 87, 0.25)',
                  borderRadius: 8, padding: 14, marginBottom: 20, fontSize: 12, color: '#ff7979', lineHeight: 1.5
                }}>
                  <strong>WARNING:</strong> This action will permanently delete/terminate this resource in your AWS account. Pre-deletion safety verification will ensure no accidental collisions occur before sandboxed deletion.
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', marginBottom: 24 }}>
                  <input
                    type="checkbox"
                    checked={deleteConfirmed}
                    onChange={e => setDeleteConfirmed(e.target.checked)}
                    style={{ width: 18, height: 18, accentColor: '#ff4757' }}
                  />
                  <span style={{ fontSize: 13, color: '#fff', fontWeight: 600 }}>
                    I authorize the immediate termination of this component.
                  </span>
                </label>
              </>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button 
                onClick={() => setSelectedForDelete(null)}
                className="btn btn-sm"
                style={{ background: 'rgba(255,255,255,0.06)', color: '#fff' }}
              >
                {deleteResult?.success ? "Close" : "Cancel"}
              </button>

              {!deleteResult?.success && (
                <button
                  onClick={handleConfirmDelete}
                  disabled={!deleteConfirmed || deleting}
                  className="btn btn-sm btn-danger"
                  style={{
                    background: deleteConfirmed ? '#ff4757' : 'rgba(255, 71, 87, 0.3)',
                    color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 6,
                    padding: '8px 18px'
                  }}
                >
                  {deleting ? <RefreshCw className="animate-spin" size={14} /> : <Trash2 size={14} />}
                  <span>{deleting ? "Terminating in AWS..." : "Confirm & Terminate Now"}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
