import { useState, useEffect, useRef } from 'react';
import { 
  Bot, Play, AlertTriangle, CheckCircle, XCircle, Clock, 
  ArrowRight, ShieldAlert, Sparkles, Send, RefreshCw, Server, 
  Box, Database, Zap, ExternalLink, HelpCircle
} from 'lucide-react';
import { fetchWithConfig, createAgentWebSocket } from '../api';

function AgentControlCenter({ user }) {
  const [prompt, setPrompt] = useState('Find the AWS resources that are costing me money but appear unused.');
  const [agentStatus, setAgentStatus] = useState('IDLE'); // IDLE, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED
  const [currentRun, setCurrentRun] = useState(null);
  const [activityLogs, setActivityLogs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [aiModal, setAiModal] = useState({ open: false, resourceId: '', text: '', loading: false });
  const logsEndRef = useRef(null);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activityLogs]);

  // Request browser notification permission on mount
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  // Connect WebSocket for live streaming
  useEffect(() => {
    const ws = createAgentWebSocket(
      (event) => {
        if (event.type === 'agent_activity') {
          setActivityLogs(prev => [...prev, {
            stage: event.stage,
            message: event.message,
            level: event.level || 'info',
            timestamp: new Date().toLocaleTimeString(),
            data: event.data
          }]);
          if (event.stage === 'WAITING_APPROVAL') {
            setAgentStatus('WAITING_APPROVAL');
            triggerBrowserNotification("CloudJanitor Needs Your Approval", event.message);
            loadRunDetails(event.run_id);
          } else if (event.stage === 'COMPLETED') {
            setAgentStatus('COMPLETED');
            loadRunDetails(event.run_id);
          } else if (event.stage === 'FAILED') {
            setAgentStatus('FAILED');
          }
        } else if (event.type === 'approval_updated') {
          // Refresh approvals list
          loadLatestRun();
        }
      },
      () => {
        setActivityLogs(prev => [...prev, {
          stage: 'CONNECTED',
          message: 'Real-time WebSocket connected to CloudJanitor agent harness.',
          level: 'info',
          timestamp: new Date().toLocaleTimeString()
        }]);
      }
    );

    loadLatestRun();

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const triggerBrowserNotification = (title, body) => {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, {
        body,
        icon: "/favicon.ico"
      });
    }
  };

  const loadLatestRun = async () => {
    try {
      const runs = await fetchWithConfig('/agent/runs');
      if (runs && runs.length > 0) {
        const latest = runs[0];
        setCurrentRun(latest);
        setAgentStatus(latest.status);
        await loadRunDetails(latest.id);
      }
    } catch (err) {
      console.error("Failed to load latest run:", err);
    }
  };

  const loadRunDetails = async (runId) => {
    try {
      const detail = await fetchWithConfig(`/agent/runs/${runId}`);
      if (detail) {
        setCandidates(detail.candidates || []);
        setApprovals(detail.approvals || []);
        if (detail.run) {
          setAgentStatus(detail.run.status);
          setCurrentRun(detail.run);
        }
      }
    } catch (err) {
      console.error("Failed to load run details:", err);
    }
  };

  const handleStartScan = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;
    setLoading(true);
    setAgentStatus('RUNNING');
    setActivityLogs([{
      stage: 'INITIATED',
      message: `User triggered agent: "${prompt}"`,
      level: 'info',
      timestamp: new Date().toLocaleTimeString()
    }]);

    try {
      const res = await fetchWithConfig('/agent/run', {
        method: 'POST',
        body: JSON.stringify({ prompt })
      });
      setCurrentRun(res);
      setAgentStatus(res.status);
      await loadRunDetails(res.id);
    } catch (err) {
      setActivityLogs(prev => [...prev, {
        stage: 'ERROR',
        message: `Agent execution failed: ${err.message}`,
        level: 'error',
        timestamp: new Date().toLocaleTimeString()
      }]);
      setAgentStatus('FAILED');
    }
    setLoading(false);
  };

  const handleApprove = async (approvalId) => {
    try {
      await fetchWithConfig(`/approvals/${approvalId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Approved in Agent Control Center', auto_execute: false })
      });
      loadRunDetails(currentRun.id);
    } catch (err) {
      alert(`Approval failed: ${err.message}`);
    }
  };

  const handleApproveAndTerminate = async (approvalId) => {
    if (!window.confirm("CONFIRMATION: You are granting permission to terminate this cloud resource. The agent will execute termination automatically inside the security sandbox. Proceed?")) {
      return;
    }
    try {
      await fetchWithConfig(`/approvals/${approvalId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Approved with auto-terminate instruction from Agent Console', auto_execute: true })
      });
      loadRunDetails(currentRun.id);
    } catch (err) {
      alert(`Auto-termination failed: ${err.message}`);
    }
  };

  const handleApproveAllPending = async () => {
    if (pendingApprovals.length === 0) return;
    if (!window.confirm(`CRITICAL: Are you sure you want to approve and automatically terminate all ${pendingApprovals.length} pending resources?`)) {
      return;
    }
    setLoading(true);
    for (const item of pendingApprovals) {
      try {
        await fetchWithConfig(`/approvals/${item.id}/approve`, {
          method: 'POST',
          body: JSON.stringify({ reason: 'Batch approved with auto-terminate from Agent Console', auto_execute: true })
        });
      } catch (err) {
        console.error(`Failed to auto-terminate ${item.id}:`, err);
      }
    }
    setLoading(false);
    loadRunDetails(currentRun.id);
  };

  const handleReject = async (approvalId) => {
    try {
      await fetchWithConfig(`/approvals/${approvalId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Rejected in Agent Control Center' })
      });
      loadRunDetails(currentRun.id);
    } catch (err) {
      alert(`Rejection failed: ${err.message}`);
    }
  };

  const handleAskAI = async (resourceId) => {
    setAiModal({ open: true, resourceId, text: '', loading: true });
    try {
      const res = await fetchWithConfig('/agent/ask', {
        method: 'POST',
        body: JSON.stringify({ resource_id: resourceId, question: 'Why is this resource identified as waste?' })
      });
      setAiModal({ open: true, resourceId, text: res.explanation, loading: false });
    } catch (err) {
      setAiModal({ open: true, resourceId, text: `AI Reasoning unavailable: ${err.message}`, loading: false });
    }
  };

  const pendingApprovals = approvals.filter(a => a.status === 'PENDING');
  const wasteCandidates = candidates.filter(c => c.is_waste);

  return (
    <div className="fade-in pb-12">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ margin: 0 }}>Agent Control Center</h1>
            <span style={{
              background: agentStatus === 'WAITING_APPROVAL' ? '#f39c12' : (agentStatus === 'RUNNING' ? '#6c5ce7' : '#2ed573'),
              color: '#fff', fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 12
            }}>
              {agentStatus}
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Autonomous Cloud Cost Janitor powered by TrueForge & AWS Live Infrastructure
          </p>
        </div>

        <button 
          onClick={loadLatestRun}
          className="btn btn-sm" 
          style={{ background: 'rgba(255,255,255,0.05)', color: '#a0a4a8' }}
        >
          <RefreshCw size={14} className="mr-1" /> Sync State
        </button>
      </div>

      {/* PROMINENT HUMAN APPROVAL REQUIRED BANNER */}
      {agentStatus === 'WAITING_APPROVAL' && pendingApprovals.length > 0 && (
        <div className="glass-panel animate-fade-in" style={{
          marginBottom: 24, padding: 24,
          background: 'linear-gradient(135deg, rgba(243, 156, 18, 0.15) 0%, rgba(231, 76, 60, 0.15) 100%)',
          border: '1px solid rgba(243, 156, 18, 0.4)', borderRadius: 12
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{
                background: '#f39c12', padding: 12, borderRadius: 10,
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <ShieldAlert size={28} color="#000" />
              </div>
              <div>
                <h3 style={{ margin: 0, color: '#f39c12', fontSize: 18, fontWeight: 800 }}>
                  HUMAN APPROVAL REQUIRED
                </h3>
                <div style={{ color: '#fff', marginTop: 4, fontSize: 14 }}>
                  <strong>{pendingApprovals.length} destructive cleanup actions</strong> are ready and paused at the safety gate.
                </div>
                <div style={{ color: '#2ed573', fontWeight: 700, fontSize: 13, marginTop: 2 }}>
                  Potential Monthly Savings: ${currentRun?.potential_monthly_savings?.toFixed(2)}/mo (${(currentRun?.potential_monthly_savings * 12)?.toFixed(2)}/yr)
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button
                onClick={handleApproveAllPending}
                className="btn btn-sm btn-danger"
                style={{
                  background: 'linear-gradient(135deg, #ff4757 0%, #e040fb 100%)',
                  color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 6,
                  padding: '10px 18px', boxShadow: '0 4px 15px rgba(255, 71, 87, 0.4)'
                }}
              >
                <Zap size={15} /> Approve & Auto-Terminate All ({pendingApprovals.length})
              </button>
              <a href="/approvals" className="btn btn-primary" style={{ padding: '10px 20px', textDecoration: 'none' }}>
                Open Approvals Gate <ArrowRight size={16} className="inline ml-1" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* PROMPT & DISPATCH BAR */}
      <div className="glass-panel" style={{ marginBottom: 24, padding: 20 }}>
        <form onSubmit={handleStartScan} style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 280, position: 'relative' }}>
            <input 
              type="text"
              className="premium-input"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="Give the janitor a mission (e.g. Find idle EC2 instances or orphaned EBS volumes)..."
              disabled={loading}
              style={{ width: '100%', paddingLeft: 40 }}
            />
            <Bot size={18} color="#6c5ce7" style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)' }} />
          </div>

          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={loading}
            style={{ padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 8 }}
          >
            {loading ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
            <span>{loading ? 'Janitor Investigating...' : 'Deploy Janitor Agent'}</span>
          </button>
        </form>

        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: '#a0a4a8' }}>Quick Prompts:</span>
          {[
            "Find the AWS resources that are costing me money but appear unused.",
            "Scan for orphaned EBS storage volumes.",
            "Detect idle EC2 instances with near-zero CPU.",
            "Check for unused Elastic Load Balancers without targets."
          ].map((quick, idx) => (
            <button 
              key={idx} 
              type="button" 
              onClick={() => setPrompt(quick)}
              style={{
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                color: '#ccc', borderRadius: 4, padding: '2px 8px', fontSize: 11, cursor: 'pointer'
              }}
            >
              {quick}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1fr) 1.2fr', gap: 24 }}>
        {/* LIVE ACTIVITY CONSOLE */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: 600 }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            paddingBottom: 14, borderBottom: '1px solid #ffffff10'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#2ed573' }} className="animate-pulse" />
              <h3 style={{ margin: 0, fontSize: 14 }}>Live Agent Activity Stream</h3>
            </div>
            <span style={{ fontSize: 11, color: '#a0a4a8' }}>WebSocket Live</span>
          </div>

          <div style={{
            flex: 1, overflowY: 'auto', padding: '16px 0', fontFamily: 'monospace', fontSize: 12,
            display: 'flex', flexDirection: 'column', gap: 10
          }}>
            {activityLogs.length === 0 ? (
              <div style={{ color: '#666', textAlign: 'center', padding: '40px 0' }}>
                Agent idle. Click "Deploy Janitor Agent" above to start live investigation.
              </div>
            ) : (
              activityLogs.map((log, i) => (
                <div key={i} style={{
                  padding: '8px 12px', borderRadius: 6,
                  background: log.level === 'error' ? 'rgba(255, 71, 87, 0.1)' : (log.level === 'warning' ? 'rgba(243, 156, 18, 0.1)' : 'rgba(255, 255, 255, 0.03)'),
                  borderLeft: `3px solid ${log.level === 'error' ? '#ff4757' : (log.level === 'warning' ? '#f39c12' : '#6c5ce7')}`
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#666', fontSize: 10, marginBottom: 2 }}>
                    <span style={{ color: '#a0a4a8', fontWeight: 600 }}>[{log.stage}]</span>
                    <span>{log.timestamp}</span>
                  </div>
                  <div style={{ color: log.level === 'error' ? '#ff4757' : (log.level === 'warning' ? '#f39c12' : '#e0e0e0'), lineHeight: 1.4 }}>
                    {log.message}
                  </div>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* IDENTIFIED WASTE CANDIDATES */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: 600, overflowY: 'auto' }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            paddingBottom: 14, borderBottom: '1px solid #ffffff10', marginBottom: 16
          }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 14 }}>Identified Waste Candidates</h3>
              <div style={{ fontSize: 11, color: '#a0a4a8' }}>
                {wasteCandidates.length} candidate resources discovered
              </div>
            </div>
            {wasteCandidates.length > 0 && (
              <span style={{ color: '#2ed573', fontWeight: 700, fontSize: 13 }}>
                Savings: ${wasteCandidates.reduce((acc, c) => acc + c.monthly_cost, 0).toFixed(2)}/mo
              </span>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {wasteCandidates.length === 0 ? (
              <div style={{ color: '#666', textAlign: 'center', padding: '60px 20px' }}>
                <CheckCircle size={36} color="#2ed573" style={{ margin: '0 auto 12px' }} />
                <div>No waste candidates identified yet.</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>Deploy the agent to inspect live infrastructure.</div>
              </div>
            ) : (
              wasteCandidates.map((cand) => {
                const approval = approvals.find(a => a.resource_id === cand.resource_id);
                return (
                  <div key={cand.resource_id} style={{
                    padding: 16, borderRadius: 10, background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {cand.resource_type === 'ec2' && <Server size={18} color="#6c5ce7" />}
                        {cand.resource_type === 'ebs' && <Box size={18} color="#f39c12" />}
                        {cand.resource_type === 'elb' && <Zap size={18} color="#2ed573" />}
                        <div>
                          <div style={{ fontWeight: 700, color: '#fff', fontSize: 14 }}>{cand.name}</div>
                          <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a4a8' }}>{cand.resource_id}</div>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{ color: '#2ed573', fontWeight: 800, fontSize: 15 }}>
                          ${cand.monthly_cost.toFixed(2)}/mo
                        </div>
                        <div style={{ fontSize: 10, color: '#a0a4a8' }}>
                          ${(cand.monthly_cost * 12).toFixed(2)}/yr savings
                        </div>
                      </div>
                    </div>

                    {/* Evidence */}
                    <div style={{ marginTop: 12, background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 6 }}>
                      <div style={{ fontSize: 11, color: '#a0a4a8', fontWeight: 600, marginBottom: 4 }}>EVIDENCE OF INACTIVITY:</div>
                      {cand.evidence && cand.evidence.map((ev, idx) => (
                        <div key={idx} style={{ fontSize: 11, color: '#ccc', lineHeight: 1.4 }}>
                          • {ev}
                        </div>
                      ))}
                    </div>

                    {/* Actions & Status */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
                      <button 
                        onClick={() => handleAskAI(cand.resource_id)}
                        className="btn btn-sm"
                        style={{
                          background: 'rgba(108, 92, 231, 0.15)', color: '#a29bfe',
                          border: '1px solid rgba(108, 92, 231, 0.3)', display: 'flex', alignItems: 'center', gap: 4
                        }}
                      >
                        <Sparkles size={12} /> AI Reasoning
                      </button>

                      {approval ? (
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          {approval.status === 'PENDING' ? (
                            <>
                              <button 
                                onClick={() => handleApproveAndTerminate(approval.id)}
                                className="btn btn-sm btn-danger"
                                style={{
                                  background: 'linear-gradient(135deg, #ff4757 0%, #e040fb 100%)',
                                  color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 4,
                                  boxShadow: '0 2px 8px rgba(255, 71, 87, 0.3)'
                                }}
                              >
                                <Zap size={12} /> Approve & Terminate Now
                              </button>
                              <button 
                                onClick={() => handleApprove(approval.id)}
                                className="btn btn-sm"
                                style={{ background: 'rgba(46, 213, 115, 0.2)', color: '#2ed573', border: '1px solid #2ed57350', fontWeight: 600 }}
                              >
                                Review Only
                              </button>
                              <button 
                                onClick={() => handleReject(approval.id)}
                                className="btn btn-sm"
                                style={{ background: 'rgba(255,255,255,0.05)', color: '#a0a4a8' }}
                              >
                                Reject
                              </button>
                            </>
                          ) : (
                            <span style={{
                              fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                              background: approval.status === 'APPROVED' ? '#2ed57320' : '#ff475720',
                              color: approval.status === 'APPROVED' ? '#2ed573' : '#ff4757'
                            }}>
                              Status: {approval.status}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span style={{ fontSize: 11, color: '#a0a4a8' }}>
                          Action: {cand.recommended_action}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* AI Reasoning Modal */}
      {aiModal.open && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(5px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="glass-panel" style={{ maxWidth: 600, width: '90%', padding: 24, borderRadius: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Sparkles size={20} color="#6c5ce7" />
                <h3 style={{ margin: 0 }}>TrueFoundry / Polaris AI Reasoning</h3>
              </div>
              <button onClick={() => setAiModal({ open: false, resourceId: '', text: '', loading: false })} className="btn btn-sm">✕</button>
            </div>

            <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a4a8', marginBottom: 14 }}>
              Resource: {aiModal.resourceId}
            </div>

            {aiModal.loading ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#a0a4a8' }}>
                <RefreshCw className="animate-spin mb-2" size={32} color="#6c5ce7" />
                <div>Consulting TrueFoundry AI Gateway (vm-polaris/openai)...</div>
              </div>
            ) : (
              <div style={{
                background: 'rgba(0,0,0,0.3)', padding: 16, borderRadius: 8,
                fontSize: 13, lineHeight: 1.6, color: '#e0e0e0', whiteSpace: 'pre-wrap'
              }}>
                {aiModal.text}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentControlCenter;
