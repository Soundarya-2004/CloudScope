import { useState, useEffect } from 'react';
import { fetchWithConfig } from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AlertCircle, Server, DollarSign, Database, Box, Play, Square, Activity, Trash2 } from 'lucide-react';

function Dashboard({ user }) {
  const [activeTab, setActiveTab] = useState('Overview');
  const [data, setData] = useState({
    ec2: [], s3: [], rds: [], lambda: []
  });
  const [costs, setCosts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isAdmin = user?.role === 'Admin';

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [ec2Res, s3Res, rdsRes, lambdaRes, costRes] = await Promise.all([
        fetchWithConfig('/aws/ec2').catch(() => ({ instances: [] })),
        fetchWithConfig('/aws/s3').catch(() => []),
        fetchWithConfig('/aws/rds').catch(() => []),
        fetchWithConfig('/aws/lambda').catch(() => []),
        fetchWithConfig('/aws/cost').catch(() => null)
      ]);
      setData({
        ec2: ec2Res.instances || [],
        s3: Array.isArray(s3Res) ? s3Res : [],
        rds: Array.isArray(rdsRes) ? rdsRes : [],
        lambda: Array.isArray(lambdaRes) ? lambdaRes : []
      });
      setCosts(costRes);
    } catch (err) {
      setError('Ensure AWS Setup is configured with valid IAM Keys.');
    }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const handleAction = async (endpoint, message) => {
    if (!isAdmin) {
      alert("You need Admin privileges to perform this action.");
      return;
    }
    if (!window.confirm(message)) return;
    try {
      if (endpoint.includes('s3/delete')) {
        await fetchWithConfig(endpoint, { method: 'DELETE' });
      } else {
        await fetchWithConfig(endpoint, { method: 'POST' });
      }
      loadData();
    } catch(err) {
      alert(`Action failed: ${err.message}`);
    }
  };

  const chartData = [];
  if (costs && costs.dates) {
    for (let i = 0; i < costs.dates.length; i++) {
      chartData.push({
        date: costs.dates[i],
        historical: costs.historical_costs[i],
        predicted: costs.predicted_costs[i]
      });
    }
  }
  
  const runningCount = data.ec2.filter(i => i.state === 'running').length;
  const bucketCount = data.s3.length;
  const activeRDS = data.rds.filter(i => i.state === 'available').length;

  if (loading) return <div className="p-4 fade-in">Loading Cloud Dashboard...</div>;
  
  return (
    <div className="fade-in pb-10">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1>Infrastructure Dashboard</h1>
        {error && <span style={{ color: 'var(--danger-color)' }}><AlertCircle className="inline" size={16}/> {error}</span>}
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
              borderBottom: activeTab === t ? '2px solid var(--accent-color)' : '2px solid transparent'
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {activeTab === 'Overview' && (
        <div className="animate-fade-in">
          <div className="dashboard-grid">
            <div className="glass-panel stat-card" onClick={() => setActiveTab('EC2')} style={{cursor:'pointer'}}>
              <h3 style={{color: '#a0a4a8'}}><Server size={18} className="inline mr-1"/> Running EC2</h3>
              <div className="stat-value">{runningCount}</div>
            </div>
            <div className="glass-panel stat-card" onClick={() => setActiveTab('S3')} style={{cursor:'pointer'}}>
              <h3 style={{color: '#a0a4a8'}}><Box size={18} className="inline mr-1"/> S3 Buckets</h3>
              <div className="stat-value">{bucketCount}</div>
            </div>
            <div className="glass-panel stat-card" onClick={() => setActiveTab('RDS')} style={{cursor:'pointer'}}>
              <h3 style={{color: '#a0a4a8'}}><Database size={18} className="inline mr-1"/> Active RDS</h3>
              <div className="stat-value">{activeRDS}</div>
            </div>
            <div className="glass-panel stat-card">
              <h3 style={{color: '#a0a4a8'}}><Activity size={18} className="inline mr-1"/> AWS Cost</h3>
              <div className="stat-value" style={{color: 'var(--accent-color)'}}>ML Projection</div>
            </div>
          </div>

          <div className="glass-panel" style={{marginBottom: '32px'}}>
            <h2>Cost Trend & Forecast (Next 30 Days)</h2>
            <div style={{width: '100%', height: 320, marginTop: 16}}>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0a" />
                    <XAxis dataKey="date" stroke="#a0a4a8" fontSize={12} tickMargin={10} />
                    <YAxis stroke="#a0a4a8" fontSize={12} tickFormatter={(v) => `$${v}`} />
                    <Tooltip contentStyle={{backgroundColor: 'rgba(31, 33, 40, 0.9)', backdropFilter: 'blur(10px)', border: '1px solid #ffffff15', borderRadius: '8px'}} />
                    <Legend iconType="circle" />
                    <Line type="monotone" dataKey="historical" stroke="#2ed573" strokeWidth={3} dot={false} name="Actual Cost" />
                    <Line type="monotone" dataKey="predicted" stroke="#6c5ce7" strokeWidth={3} dot={false} strokeDasharray="5 5" name="Projected Cost (ML)" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div style={{display:'flex', height:'100%', alignItems:'center', justifyContent:'center'}}>
                  <p style={{color: 'var(--text-secondary)'}}>No cost explorer data. AWS account may be too new.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'EC2' && (
        <div className="glass-panel animate-fade-in">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
             <h2>Compute (EC2)</h2>
             {!isAdmin && <span style={{fontSize: 12, color: 'var(--danger-color)'}}>View-only Mode</span>}
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Instance Name</th><th>ID</th><th>Type</th><th>State</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.ec2.map(inst => (
                  <tr key={inst.id}>
                    <td style={{fontWeight: 'bold'}}>{inst.name}</td>
                    <td style={{color: 'var(--text-secondary)'}}>{inst.id}</td>
                    <td>{inst.type}</td>
                    <td><span className={`status-badge status-${inst.state === 'running' ? 'running' : 'stopped'}`}>{inst.state}</span></td>
                    <td>
                      {inst.state !== 'terminated' && (
                        <button onClick={() => handleAction(`/aws/ec2/terminate/${inst.id}`, `Terminate EC2 instance ${inst.id}?`)} className="btn btn-danger btn-sm" disabled={!isAdmin}>
                          <Square size={14} className="inline mr-1"/> Terminate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {data.ec2.length === 0 && <tr><td colSpan="5" style={{textAlign:'center', color: 'var(--text-secondary)'}}>No EC2 instances found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'S3' && (
        <div className="glass-panel animate-fade-in">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
             <h2>Storage (S3)</h2>
             {!isAdmin && <span style={{fontSize: 12, color: 'var(--danger-color)'}}>View-only Mode</span>}
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Bucket Name</th><th>Creation Date</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.s3.map(b => (
                  <tr key={b.name}>
                    <td style={{fontWeight: 'bold'}}>{b.name}</td>
                    <td>{new Date(b.creation_date).toLocaleDateString()}</td>
                    <td>
                      <button onClick={() => handleAction(`/aws/s3/delete/${b.name}`, `Delete S3 Bucket ${b.name}? This might fail if the bucket is not empty.`)} className="btn btn-danger btn-sm" disabled={!isAdmin}>
                        <Trash2 size={14} className="inline mr-1"/> Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {data.s3.length === 0 && <tr><td colSpan="3" style={{textAlign:'center', color: 'var(--text-secondary)'}}>No S3 buckets found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'RDS' && (
        <div className="glass-panel animate-fade-in">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
             <h2>Databases (RDS)</h2>
             {!isAdmin && <span style={{fontSize: 12, color: 'var(--danger-color)'}}>View-only Mode</span>}
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>DB Identifier</th><th>Engine</th><th>Class</th><th>State</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.rds.map(db => (
                  <tr key={db.id}>
                    <td style={{fontWeight: 'bold'}}>{db.id}</td>
                    <td>{db.engine}</td>
                    <td>{db.size}</td>
                    <td><span className={`status-badge status-${db.state === 'available' ? 'running' : 'stopped'}`}>{db.state}</span></td>
                    <td>
                      {db.state === 'available' && (
                        <button onClick={() => handleAction(`/aws/rds/stop/${db.id}`, `Stop RDS database ${db.id}?`)} className="btn btn-warning btn-sm" disabled={!isAdmin}>
                          <Square size={14} className="inline mr-1"/> Stop
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {data.rds.length === 0 && <tr><td colSpan="5" style={{textAlign:'center', color: 'var(--text-secondary)'}}>No RDS instances found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'Lambda' && (
        <div className="glass-panel animate-fade-in">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
             <h2>Serverless (Lambda)</h2>
          </div>
          <div className="table-container mt-4">
            <table>
              <thead>
                <tr>
                  <th>Function Name</th><th>Runtime</th><th>State</th><th>Last Modified</th>
                </tr>
              </thead>
              <tbody>
                {data.lambda.map(fn => (
                  <tr key={fn.name}>
                    <td style={{fontWeight: 'bold'}}>{fn.name}</td>
                    <td>{fn.runtime}</td>
                    <td><span className={`status-badge status-running`}>{fn.state}</span></td>
                    <td>{new Date(fn.last_modified).toLocaleDateString()}</td>
                  </tr>
                ))}
                {data.lambda.length === 0 && <tr><td colSpan="4" style={{textAlign:'center', color: 'var(--text-secondary)'}}>No Lambda functions found.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
