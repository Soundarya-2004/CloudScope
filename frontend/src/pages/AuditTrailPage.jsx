import { useState, useEffect } from 'react';
import { Shield, CheckCircle, AlertTriangle, XCircle, Clock, RefreshCw, Filter } from 'lucide-react';
import { fetchWithConfig } from '../api';

function AuditTrailPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');

  const loadAuditEvents = async () => {
    setLoading(true);
    try {
      const url = actionFilter ? `/audit?action=${actionFilter}` : '/audit';
      const data = await fetchWithConfig(url);
      setEvents(data || []);
    } catch (err) {
      console.error("Failed to load audit events:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadAuditEvents();
  }, [actionFilter]);

  return (
    <div className="fade-in pb-12">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>Audit Trail & Governance Log</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Immutable, chronologically ordered log of every agent action, approval decision, and cloud API call
          </p>
        </div>

        <button onClick={loadAuditEvents} className="btn btn-sm">
          <RefreshCw size={14} className="mr-1" /> Refresh
        </button>
      </div>

      {/* FILTER BAR */}
      <div className="glass-panel" style={{ padding: '12px 20px', marginBottom: 20, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <Filter size={16} color="#a0a4a8" />
        <span style={{ fontSize: 12, color: '#a0a4a8' }}>Filter Action:</span>
        <select 
          value={actionFilter} 
          onChange={e => setActionFilter(e.target.value)}
          className="premium-input"
          style={{ width: 220, padding: '6px 10px', fontSize: 12 }}
        >
          <option value="">All Actions</option>
          <option value="AGENT_STARTED">AGENT_STARTED</option>
          <option value="AWS_CONNECTED">AWS_CONNECTED</option>
          <option value="DISCOVERY_STARTED">DISCOVERY_STARTED</option>
          <option value="CANDIDATE_IDENTIFIED">CANDIDATE_IDENTIFIED</option>
          <option value="PLAN_GENERATED">PLAN_GENERATED</option>
          <option value="APPROVAL_REQUESTED">APPROVAL_REQUESTED</option>
          <option value="APPROVAL_APPROVED">APPROVAL_APPROVED</option>
          <option value="APPROVAL_REJECTED">APPROVAL_REJECTED</option>
          <option value="EXECUTION_STARTED">EXECUTION_STARTED</option>
          <option value="EXECUTION_COMPLETED">EXECUTION_COMPLETED</option>
          <option value="EXECUTION_FAILED">EXECUTION_FAILED</option>
        </select>
      </div>

      {/* EVENTS TABLE */}
      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Status</th>
                <th>Resource / Target</th>
                <th>Reason / Summary</th>
                <th>User / Agent</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: 40, color: '#a0a4a8' }}>
                    <RefreshCw className="animate-spin mb-2" size={24} />
                    <div>Loading audit trail...</div>
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: 40, color: '#a0a4a8' }}>
                    No audit events recorded yet.
                  </td>
                </tr>
              ) : (
                events.map(ev => (
                  <tr key={ev.id}>
                    <td style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a4a8', whiteSpace: 'nowrap' }}>
                      <Clock size={12} className="inline mr-1" />
                      {new Date(ev.timestamp).toLocaleString()}
                    </td>
                    <td>
                      <code style={{
                        background: '#ffffff0a', padding: '3px 8px', borderRadius: 4,
                        fontSize: 11, fontWeight: 700, color: '#fff'
                      }}>
                        {ev.action}
                      </code>
                    </td>
                    <td>
                      <span style={{
                        fontSize: 10, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
                        background: ev.status === 'SUCCESS' ? '#2ed57320' : (ev.status === 'PENDING' ? '#f39c1220' : '#ff475720'),
                        color: ev.status === 'SUCCESS' ? '#2ed573' : (ev.status === 'PENDING' ? '#f39c12' : '#ff4757')
                      }}>
                        {ev.status}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: 11, color: '#e0e0e0' }}>
                      {ev.resource_id || (ev.aws_account_id ? `Account: ${ev.aws_account_id}` : '--')}
                    </td>
                    <td style={{ fontSize: 12, color: '#ccc', maxWidth: 350 }}>
                      {ev.reason}
                    </td>
                    <td style={{ fontSize: 11, color: '#a0a4a8' }}>
                      {ev.user}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default AuditTrailPage;
