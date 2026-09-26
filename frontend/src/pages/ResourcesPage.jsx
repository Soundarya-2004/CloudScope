import { useState, useEffect } from 'react';
import { 
  Server, Box, Zap, AlertTriangle, CheckCircle, RefreshCw, 
  Database, Radio, Layers, HardDrive, Cpu, Cloud, Trash2, 
  ShieldAlert, X, AlertCircle, Sparkles
} from 'lucide-react';
import { fetchWithConfig } from '../api';

function ResourcesPage() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [wasteOnly, setWasteOnly] = useState(false);

  // Deletion Modal State
  const [selectedForDelete, setSelectedForDelete] = useState(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteResult, setDeleteResult] = useState(null);

  const loadResources = async (forceRefresh = false) => {
    if (forceRefresh) setScanning(true);
    else setLoading(true);
    try {
      const url = forceRefresh ? '/resources/scan' : `/resources?waste_only=${wasteOnly}`;
      const method = forceRefresh ? 'POST' : 'GET';
      const data = await fetchWithConfig(url, { method });
      if (forceRefresh && data.resources) {
        setResources(data.resources);
      } else {
        setResources(data || []);
      }
    } catch (err) {
      console.error("Failed to load resources:", err);
    }
    setLoading(false);
    setScanning(false);
  };

  useEffect(() => {
    loadResources();
  }, [wasteOnly]);

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
          reason: 'User directly authorized component termination via CloudScope console'
        })
      });
      setDeleteResult({
        success: true,
        message: res.message || 'Component successfully terminated and verified in AWS.'
      });
      loadResources();
    } catch (err) {
      setDeleteResult({
        success: false,
        error: err.message || 'Failed to terminate component.'
      });
    }
    setDeleting(false);
  };

  const filtered = resources.filter(r => {
    if (typeFilter === 'ALL') return true;
    if (typeFilter === 'OTHER') {
      return !['ec2', 'ebs', 'elb', 'eip', 'rds', 's3', 'lambda'].includes(r.resource_type.toLowerCase());
    }
    return r.resource_type.toLowerCase() === typeFilter.toLowerCase();
  });

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

  return (
    <div className="fade-in pb-12">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>Active AWS Infrastructure</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Elastic discovery across EC2, EBS, ELB, EIP, RDS, S3, Lambda, and dynamically identified cloud services
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button 
            onClick={() => loadResources(true)} 
            disabled={scanning || loading}
            className="btn btn-primary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            {scanning ? <RefreshCw className="animate-spin" size={14} /> : <Sparkles size={14} />}
            <span>{scanning ? "Scanning AWS Account..." : "Live Scan AWS Account"}</span>
          </button>
          <button onClick={() => loadResources(false)} className="btn btn-sm">
            <RefreshCw size={14} className="mr-1" /> Refresh
          </button>
        </div>
      </div>

      {/* FILTER BAR */}
      <div className="glass-panel" style={{ padding: '14px 20px', marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {['ALL', 'EC2', 'EBS', 'ELB', 'EIP', 'RDS', 'S3', 'LAMBDA', 'OTHER'].map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              style={{
                background: typeFilter === t ? '#6c5ce7' : 'rgba(255,255,255,0.05)',
                color: typeFilter === t ? '#fff' : '#a0a4a8',
                border: 'none', borderRadius: 6, padding: '5px 12px', fontSize: 11,
                fontWeight: 600, cursor: 'pointer'
              }}
            >
              {t}
            </button>
          ))}
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: '#e0e0e0' }}>
          <input 
            type="checkbox" 
            checked={wasteOnly} 
            onChange={e => setWasteOnly(e.target.checked)} 
            style={{ accentColor: '#ff4757', width: 16, height: 16 }}
          />
          <span>Show Potential Waste Only</span>
        </label>
      </div>

      {/* TABLE */}
      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Resource Name & ID</th>
                <th>Service Type</th>
                <th>State</th>
                <th>Monthly Cost</th>
                <th>Cost Source</th>
                <th>Status / Finding</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading || scanning ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: 40, color: '#a0a4a8' }}>
                    <RefreshCw className="animate-spin mb-2" size={24} />
                    <div>Scanning live AWS infrastructure across all account services...</div>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: 40, color: '#a0a4a8' }}>
                    No running resources found matching this filter. Click "Live Scan AWS Account" above to inspect.
                  </td>
                </tr>
              ) : (
                filtered.map(r => (
                  <tr key={r.resource_id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {renderServiceIcon(r.resource_type)}
                        <div>
                          <div style={{ fontWeight: 700, color: '#fff' }}>{r.name}</div>
                          <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a4a8', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {r.resource_id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <code style={{ fontSize: 11, textTransform: 'uppercase' }}>
                        {r.resource_type}
                      </code>
                    </td>
                    <td>
                      <span className={`status-badge status-${['running', 'available', 'active'].includes(r.state?.toLowerCase()) ? 'running' : 'stopped'}`}>
                        {r.state}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: r.is_waste ? '#2ed573' : '#fff' }}>
                      ${r.monthly_cost ? r.monthly_cost.toFixed(2) : '0.00'}/mo
                    </td>
                    <td style={{ fontSize: 11, color: '#a0a4a8' }}>
                      {r.cost_source || 'calculated_estimate'}
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

export default ResourcesPage;
