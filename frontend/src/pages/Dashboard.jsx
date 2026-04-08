import { useState, useEffect } from 'react';
import { fetchWithConfig } from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { AlertCircle, Server, DollarSign, Database, Box, Play, Square, Activity, Trash2, Zap, Clock, RefreshCw } from 'lucide-react';

function Dashboard({ user }) {
  const [activeTab, setActiveTab] = useState('Overview');
  const [data, setData] = useState({
    ec2: [], s3: [], rds: [], lambda: []
  });
  const [costs, setCosts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [status, setStatus] = useState({
    ec2: 'ok', s3: 'ok', rds: 'ok', lambda: 'ok', cost: 'ok'
  });

  const isAdmin = user?.role === 'Admin';

  const loadData = async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetchWithConfig('/aws/ec2'),
        fetchWithConfig('/aws/s3'),
        fetchWithConfig('/aws/rds'),
        fetchWithConfig('/aws/lambda'),
        fetchWithConfig('/aws/cost')
      ]);

      const [ec2Res, s3Res, rdsRes, lambdaRes, costRes] = results;

      setData({
        ec2: ec2Res.status === 'fulfilled' ? (ec2Res.value.instances || []) : [],
        s3: s3Res.status === 'fulfilled' ? (Array.isArray(s3Res.value) ? s3Res.value : []) : [],
        rds: rdsRes.status === 'fulfilled' ? (Array.isArray(rdsRes.value) ? rdsRes.value : []) : [],
        lambda: lambdaRes.status === 'fulfilled' ? (Array.isArray(lambdaRes.value) ? lambdaRes.value : []) : []
      });

      setStatus({
        ec2: ec2Res.status === 'fulfilled' ? 'ok' : 'error',
        s3: s3Res.status === 'fulfilled' ? 'ok' : 'error',
        rds: rdsRes.status === 'fulfilled' ? 'ok' : 'error',
        lambda: lambdaRes.status === 'fulfilled' ? 'ok' : 'error',
        cost: costRes.status === 'fulfilled' ? 'ok' : 'error'
      });

      if (costRes.status === 'fulfilled') {
        setCosts(costRes.value);
      }
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Dashboard load error:", err);
    }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const handleAction = async (endpoint, message) => {
    if (!isAdmin) {
      alert("Admin privileges required for this action.");
      return;
    }
    if (!window.confirm(message)) return;
    try {
      const method = endpoint.includes('delete') ? 'DELETE' : 'POST';
      await fetchWithConfig(endpoint, { method });
      loadData();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    }
  };

  const chartData = [];
  if (costs && costs.dates) {
    for (let i = 0; i < costs.dates.length; i++) {
      const dateObj = new Date(costs.dates[i]);
      chartData.push({
        date: dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        fullDate: costs.dates[i],
        historical: costs.historical_costs[i],
        predicted: costs.predicted_costs[i]
      });
    }
  }

  const runningCount = data.ec2.filter(i => i.state === 'running').length;
  const bucketCount = data.s3.length;
  const activeRDS = data.rds.filter(i => i.state === 'available').length;
  const lambdaCount = data.lambda.length;

  if (loading && !lastUpdated) return (
    <div className="flex-col center" style={{ height: '80vh' }}>
      <RefreshCw className="animate-spin mb-4" size={40} color="var(--accent-color)" />
      <div className="text-secondary">Synchronizing with AWS Infrastructure...</div>
    </div>
  );

  return (
    <div className="fade-in pb-10">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1>Infrastructure Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
            <Clock size={12} className="inline mr-1" /> Last synced at {lastUpdated}
          </p>
        </div>
        <button onClick={loadData} className="btn btn-sm" style={{ background: 'rgba(108, 92, 231, 0.1)', color: 'var(--accent-color)' }}>
          <RefreshCw size={14} className="mr-1" /> Refresh
        </button>
      </div>

      {/* TABS */}
      <div className="tabs-container" style={{ display: 'flex', gap: 16, marginBottom: 24, borderBottom: '1px solid #ffffff15', paddingBottom: 12 }}>
        {['Overview', 'EC2', 'S3', 'RDS', 'Lambda'].map(t => (
          <button
            key={t}
            className={`tab-btn ${activeTab === t ? 'active' : ''}`}
            onClick={() => setActiveTab(t)}
            style={{
              background: 'transparent', border: 'none', color: activeTab === t ? '#fff' : '#a0a4a8',
              fontSize: 16, fontWeight: activeTab === t ? '600' : '400', cursor: 'pointer', padding: '8px 16px',
              borderBottom: activeTab === t ? '2px solid var(--accent-color)' : '2px solid transparent',
              display: 'flex', alignItems: 'center', gap: 8
            }}
          >
            {t === 'Overview' && <Activity size={16} />}
            {t === 'EC2' && <Server size={16} />}
            {t === 'S3' && <Box size={16} />}
            {t === 'RDS' && <Database size={16} />}
            {t === 'Lambda' && <Zap size={16} />}
            {t}
            {status[t.toLowerCase()] === 'error' && <AlertCircle size={12} color="var(--danger-color)" />}
          </button>
        ))}
      </div>

      {activeTab === 'Overview' && (
        <div className="animate-fade-in">
          <div className="dashboard-grid">
            <div className="glass-panel stat-card" onClick={() => setActiveTab('EC2')} style={{ cursor: 'pointer' }}>
              <h3 style={{ color: '#a0a4a8' }}><Server size={18} className="inline mr-1" /> Running EC2</h3>
              <div className="stat-value">{runningCount}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>Active instances in {user?.aws_region || 'us-east-1'}</div>
            </div>
            <div className="glass-panel stat-card" onClick={() => setActiveTab('S3')} style={{ cursor: 'pointer' }}>
              <h3 style={{ color: '#a0a4a8' }}><Box size={18} className="inline mr-1" /> S3 Buckets</h3>
              <div className="stat-value">{bucketCount}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>Global storage resources</div>
            </div>
            <div className="glass-panel stat-card" onClick={() => setActiveTab('RDS')} style={{ cursor: 'pointer' }}>
              <h3 style={{ color: '#a0a4a8' }}><Database size={18} className="inline mr-1" /> Active RDS</h3>
              <div className="stat-value">{activeRDS}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>Managed database clusters</div>
            </div>
            <div className="glass-panel stat-card">
              <h3 style={{ color: '#a0a4a8' }}><DollarSign size={18} className="inline mr-1" /> Month-to-Date</h3>
              <div className="stat-value" style={{ color: 'var(--accent-color)' }}>${costs?.total_current_month?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              <div style={{ fontSize: 12, color: 'var(--success-color)', marginTop: 8 }}>Real-time Cost Explorer data</div>
            </div>
          </div>

          <div className="glass-panel" style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <h2>Cost Trend & ML Forecast</h2>
                <div style={{ color: '#a0a4a8', fontSize: 13 }}>Predictive analysis for the next 30 days</div>
              </div>
              <div className="glass-panel" style={{ padding: '12px 20px', background: 'rgba(108, 92, 231, 0.1)', border: '1px solid rgba(108, 92, 231, 0.2)' }}>
                <span style={{ color: '#a0a4a8', fontSize: 13 }}>Projected Monthly Total: </span>
                <span style={{ color: 'var(--accent-color)', fontWeight: '800', fontSize: 22, marginLeft: 8 }}>${costs?.total_projected?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</span>
              </div>
            </div>
            <div style={{ width: '100%', height: 350, marginTop: 24 }}>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="colorHist" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2ed573" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#2ed573" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorPred" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6c5ce7" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6c5ce7" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0a" />
                    <XAxis dataKey="date" stroke="#a0a4a8" fontSize={11} tickMargin={10} axisLine={false} tickLine={false} />
                    <YAxis stroke="#a0a4a8" fontSize={11} tickFormatter={(v) => `$${v}`} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'rgba(15, 16, 20, 0.95)', backdropFilter: 'blur(10px)', border: '1px solid #ffffff15', borderRadius: '12px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }}
                      itemStyle={{ fontSize: 13 }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: 20 }} />
                    <Area type="monotone" dataKey="historical" stroke="#2ed573" strokeWidth={3} fillOpacity={1} fill="url(#colorHist)" name="Actual Cost" dot={{ r: 2 }} />
                    <Area type="monotone" dataKey="predicted" stroke="#6c5ce7" strokeWidth={3} strokeDasharray="5 5" fillOpacity={1} fill="url(#colorPred)" name="ML Projection" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                  <div className="flex-col center">
                    <AlertCircle size={32} color="#a0a4a8" className="mb-2" />
                    <p style={{ color: 'var(--text-secondary)' }}>Initializing Cost Explorer. AWS data may take 24h to populate.</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {costs?.services && Object.keys(costs.services).length > 0 && (
            <div className="glass-panel animate-fade-in" style={{ marginBottom: '32px' }}>
              <h2>Resource Cost Breakdown</h2>
              <div className="grid-3" style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
                {Object.entries(costs.services).map(([service, amount]) => (
                  <div key={service} className="stat-card" style={{ padding: 20, background: '#ffffff03', borderRadius: '12px', border: '1px solid #ffffff08' }}>
                    <div style={{ fontSize: 12, color: '#a0a4a8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>{service}</div>
                    <div style={{ fontSize: 24, fontWeight: '800', color: '#fff' }}>${amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                    <div style={{ width: '100%', height: 4, background: '#ffffff0a', borderRadius: 2, marginTop: 12 }}>
                      <div style={{ width: `${Math.min(100, (amount / costs.total_current_month) * 100)}%`, height: '100%', background: 'var(--accent-color)', borderRadius: 2 }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'EC2' && (
        <div className="glass-panel animate-fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Compute Instances (EC2)</h2>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <span className="status-badge status-running" style={{ fontSize: 11 }}>Total: {data.ec2.length}</span>
              {!isAdmin && <span style={{ fontSize: 12, color: 'var(--danger-color)' }}>View-only Mode</span>}
            </div>
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Instance Name</th><th>Instance ID</th><th>Type</th><th>Region</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.ec2.map(inst => (
                  <tr key={inst.id}>
                    <td style={{ fontWeight: '700', color: '#fff' }}>{inst.name}</td>
                    <td style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{inst.id}</td>
                    <td><code style={{ background: '#ffffff0a', padding: '2px 6px', borderRadius: 4 }}>{inst.type}</code></td>
                    <td style={{ color: '#a0a4a8' }}>{user?.aws_region || 'us-east-1'}</td>
                    <td><span className={`status-badge status-${inst.state === 'running' ? 'running' : 'stopped'}`}>{inst.state}</span></td>
                    <td>
                      {inst.state !== 'terminated' ? (
                        <button onClick={() => handleAction(`/aws/ec2/terminate/${inst.id}`, `Terminate EC2 instance ${inst.id}?`)} className="btn btn-danger btn-sm" disabled={!isAdmin}>
                          <Trash2 size={14} className="mr-1" /> Terminate
                        </button>
                      ) : <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Finalized</span>}
                    </td>
                  </tr>
                ))}
                {data.ec2.length === 0 && <tr><td colSpan="6" style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>No active EC2 instances found in this region.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'S3' && (
        <div className="glass-panel animate-fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Object Storage (S3)</h2>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <span className="status-badge status-running" style={{ fontSize: 11 }}>Buckets: {data.s3.length}</span>
              {!isAdmin && <span style={{ fontSize: 12, color: 'var(--danger-color)' }}>View-only Mode</span>}
            </div>
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Bucket Name</th><th>Estimated Size</th><th>Created On</th><th>Public Access</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.s3.map(b => (
                  <tr key={b.name}>
                    <td style={{ fontWeight: '700', color: '#fff' }}>{b.name}</td>
                    <td>{b.size_mb > 0 ? `${b.size_mb.toFixed(1)} MB` : '--'}</td>
                    <td>{new Date(b.creation_date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}</td>
                    <td><span className="status-badge" style={{ background: '#ffffff05', color: '#a0a4a8' }}>Block Public</span></td>
                    <td>
                      <button onClick={() => handleAction(`/aws/s3/delete/${b.name}`, `Permanently delete S3 Bucket ${b.name}?`)} className="btn btn-danger btn-sm" disabled={!isAdmin}>
                        <Trash2 size={14} className="mr-1" /> Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {data.s3.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>No S3 storage buckets detected.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'RDS' && (
        <div className="glass-panel animate-fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Managed Databases (RDS)</h2>
            {!isAdmin && <span style={{ fontSize: 12, color: 'var(--danger-color)' }}>View-only Mode</span>}
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Identifier</th><th>Engine</th><th>Instance Class</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.rds.map(db => (
                  <tr key={db.id}>
                    <td style={{ fontWeight: '700', color: '#fff' }}>{db.id}</td>
                    <td style={{ textTransform: 'capitalize' }}>{db.engine}</td>
                    <td><code>{db.size}</code></td>
                    <td><span className={`status-badge status-${db.state === 'available' ? 'running' : 'stopped'}`}>{db.state}</span></td>
                    <td>
                      {db.state === 'available' && (
                        <button onClick={() => handleAction(`/aws/rds/stop/${db.id}`, `Suspend RDS database ${db.id}?`)} className="btn btn-warning btn-sm" disabled={!isAdmin}>
                          <Square size={14} className="mr-1" /> Stop
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {data.rds.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>No RDS database instances found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'Lambda' && (
        <div className="glass-panel animate-fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Serverless Functions (Lambda)</h2>
            <span className="status-badge status-running" style={{ fontSize: 11 }}>{data.lambda.length} Functions</span>
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Function Name</th><th>Runtime environment</th><th>Memory</th><th>Last Modified</th>
                </tr>
              </thead>
              <tbody>
                {data.lambda.map(fn => (
                  <tr key={fn.name}>
                    <td style={{ fontWeight: '700', color: '#fff' }}>{fn.name}</td>
                    <td><code style={{ color: 'var(--accent-color)' }}>{fn.runtime}</code></td>
                    <td>128 MB</td>
                    <td>{new Date(fn.last_modified).toLocaleDateString()}</td>
                  </tr>
                ))}
                {data.lambda.length === 0 && <tr><td colSpan="4" style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>No Lambda functions discovered.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
