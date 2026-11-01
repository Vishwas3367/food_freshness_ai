
import React from 'react';
import {
  Brain,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Info,
  Database
} from 'lucide-react';

export default function AIPredictions({ items = [] }) {
  return (
    <>
      <div className="welcome">
        <div>
          <small className="eyebrow">
            ADAPTIVE SENSOR FUSION & ML INFERENCE
          </small>

          <h1>AI Predictions & Freshness Assessment</h1>

          <p>
            Provisional freshness-risk and reference-assisted degradation estimates for foods stored in your FreshBox.
          </p>
        </div>

        <span className="demo-badge" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' }}>
          Adaptive Baseline Inference
        </span>
      </div>

      {items.length === 0 ? (
        <div className="empty-inventory">
          <div className="empty-icon">🧠</div>

          <h2>No food batches available for assessment</h2>

          <p>
            Add a produce batch from your Dashboard to begin live sensor tracking and adaptive degradation analysis.
          </p>
        </div>
      ) : (
        <div className="prediction-list">
          {items.map((item) => {
            const score = Number(item.score ?? 80);
            const days = Number(item.days ?? 4);
            const isRef = Boolean(item.isExternalReference);

            return (
              <article
                className="prediction"
                key={item.id}
                style={{ padding: '20px', borderRadius: '12px', background: '#fff', border: '1px solid #e5e7eb', marginBottom: '16px' }}
              >
                <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                  <div
                    className="prediction-emoji"
                    style={{
                      background: item.color || '#eaf4e8',
                      fontSize: '32px',
                      width: '60px',
                      height: '60px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '12px'
                    }}
                  >
                    {item.emoji || '🥗'}
                  </div>

                  <div className="prediction-main" style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ margin: 0, fontSize: '18px' }}>{item.name}</h3>
                      <span
                        style={{
                          fontSize: '12px',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          background: score >= 70 ? '#dcfce7' : score >= 40 ? '#fef3c7' : '#fee2e2',
                          color: score >= 70 ? '#166534' : score >= 40 ? '#854d0e' : '#991b1b',
                          fontWeight: 600
                        }}
                      >
                        {score >= 70 ? 'Fresh / Low Risk' : score >= 40 ? 'Moderate Risk / Use Soon' : 'High Freshness Risk'}
                      </span>
                    </div>

                    <p style={{ margin: '6px 0', fontSize: '13px', color: '#6b7280' }}>
                      {item.category}
                      {item.quantityKg !== undefined && ` · ${Number(item.quantityKg).toFixed(2)} kg`}
                      {' · '}
                      Sensor Freshness Index: <b>{score}%</b>
                    </p>

                    <div className="track" style={{ height: '8px', background: '#e5e7eb', borderRadius: '4px', overflow: 'hidden', margin: '8px 0' }}>
                      <div
                        className="fill"
                        style={{
                          height: '100%',
                          width: `${Math.max(0, Math.min(100, score))}%`,
                          background: score >= 70 ? '#22c55e' : score >= 40 ? '#eab308' : '#ef4444',
                          transition: 'width 0.3s'
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#4b5563', marginTop: '8px' }}>
                      <span>
                        <b>Reference Source:</b> {isRef ? 'External research baseline' : 'Customer-generated baseline'}
                      </span>
                      <span>
                        <b>Sensors Active:</b> DHT22 (T/RH), MQ-135, HX711
                      </span>
                    </div>
                  </div>

                  <div className="prediction-days" style={{ textAlign: 'center', minWidth: '100px', borderLeft: '1px solid #f3f4f6', paddingLeft: '16px' }}>
                    <b style={{ fontSize: '20px', display: 'block', color: '#111827' }}>
                      ~{days} {days === 1 ? 'day' : 'days'}
                    </b>
                    <small style={{ color: '#6b7280', fontSize: '11px' }}>
                      Provisional Shelf Life
                    </small>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <div className="info-panel">
        <Brain size={22} />

        <div>
          <h2>Adaptive AI & Learning Architecture</h2>

          <p>
            FreshBox AI separates provisional sensor monitoring from scientifically validated shelf-life models. When a produce batch is first added, the system establishes an <b>individual baseline</b> from real valid physical readings and performs adaptive sensor fusion. A numerical RSL prediction is labeled as provisional until sufficient customer-observed quality outcomes and held-out validation criteria are met.
          </p>
        </div>
      </div>
    </>
  );
}

