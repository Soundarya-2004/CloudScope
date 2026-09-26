import { useState, useEffect } from 'react';
import { DollarSign, TrendingDown, ShieldCheck, AlertCircle, RefreshCw, PieChart } from 'lucide-react';
import { fetchWithConfig } from '../api';

function CostPage() {
  const [costSummary, setCostSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadCostData = async () => {
    setLoading(true);
    try {
      const data = await fetchWithConfig('/cost/summary');
      setCostSummary(data);
    } catch (err) {
      console.error("Failed to load cost summary:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadCostData();
  }, []);

  return (
    <div className="fade-in pb-12">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0 }}>Cost & Waste Analytics</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            Transparent financial accounting distinguishing real AWS billing from verified pricing estimates
          </p>
        </div>
        <button onClick={loadCostData} className="btn btn-sm">
          <RefreshCw size={14} className="mr-1" /> Refresh
        </button>
      </div>

      {/* METRIC CARDS */}
      <div className="dashboard-grid" style={{ marginBottom: 24 }}>
        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>
            <DollarSign size={18} className="inline mr-1" /> Monthly AWS Spend
          </h3>
          <div className="stat-value">
            ${costSummary?.total_monthly_spend?.toFixed(2) || '0.00'}
          </div>
          <div style={{ fontSize: 11, color: '#a0a4a8', marginTop: 6 }}>
            Status: {costSummary?.billing_data_status || 'Checking...'}
          </div>
        </div>

        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>
            <TrendingDown size={18} className="inline mr-1" /> Potential Monthly Savings
          </h3>
          <div className="stat-value" style={{ color: '#2ed573' }}>
            ${costSummary?.potential_monthly_savings?.toFixed(2) || '0.00'}
          </div>
          <div style={{ fontSize: 11, color: '#2ed573', marginTop: 6 }}>
            From {costSummary?.candidates_count || 0} identified waste candidates
          </div>
        </div>

        <div className="glass-panel stat-card">
          <h3 style={{ color: '#a0a4a8' }}>
            <ShieldCheck size={18} className="inline mr-1" /> Potential Annual Savings
          </h3>
          <div className="stat-value" style={{ color: '#6c5ce7' }}>
            ${costSummary?.potential_annual_savings?.toFixed(2) || '0.00'}
          </div>
          <div style={{ fontSize: 11, color: '#a0a4a8', marginTop: 6 }}>
            Projected 12-month return on cleanup
          </div>
        </div>
      </div>

      {/* COST SOURCE TRANSPARENCY NOTICE */}
      <div className="glass-panel" style={{ marginBottom: 24, padding: 20 }}>
        <h3 style={{ marginTop: 0, fontSize: 16 }}>Cost Engine Source Attribution</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
          CloudScope adheres to strict financial transparency standards. We never fabricate prices or silently substitute demo numbers:
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginTop: 16 }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: 14, borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontWeight: 700, color: '#2ed573', fontSize: 13 }}>AWS Cost Explorer</div>
            <div style={{ fontSize: 12, color: '#a0a4a8', marginTop: 4 }}>
              Direct unblended billing metrics from the AWS Cost Explorer API when permissions and billing tags allow.
            </div>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', padding: 14, borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontWeight: 700, color: '#6c5ce7', fontSize: 13 }}>AWS Pricing-Derived Estimates</div>
            <div style={{ fontSize: 12, color: '#a0a4a8', marginTop: 4 }}>
              Calculated using published AWS regional on-demand rates (e.g. t3.medium @ $0.0416/hr × 730h, EBS gp3 @ $0.08/GB-mo).
            </div>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', padding: 14, borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontWeight: 700, color: '#f39c12', fontSize: 13 }}>Missing Permissions Handling</div>
            <div style={{ fontSize: 12, color: '#a0a4a8', marginTop: 4 }}>
              If Cost Explorer permissions are restricted by IAM, CloudScope clearly reports "Billing data unavailable" rather than guessing.
            </div>
          </div>
        </div>
      </div>

      {/* SERVICE BREAKDOWN */}
      {costSummary?.service_breakdown && Object.keys(costSummary.service_breakdown).length > 0 && (
        <div className="glass-panel">
          <h3 style={{ marginTop: 0, fontSize: 16 }}>Monthly Spend by AWS Service</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14, marginTop: 16 }}>
            {Object.entries(costSummary.service_breakdown).map(([service, amount]) => (
              <div key={service} style={{
                background: 'rgba(255,255,255,0.03)', padding: 16, borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.06)'
              }}>
                <div style={{ fontSize: 11, color: '#a0a4a8', textTransform: 'uppercase', marginBottom: 6 }}>
                  {service}
                </div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>
                  ${amount.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default CostPage;
