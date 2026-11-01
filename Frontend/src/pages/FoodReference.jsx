import React, { useEffect, useState } from 'react';
import { Leaf, Database, CheckCircle2, AlertCircle, Cpu, Thermometer, Wind, Scale } from 'lucide-react';
import { foodItems } from '../data/foodData.js';

const API_BASE_URL = (
  import.meta.env.VITE_FRESHBOX_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

export default function FoodReference() {
  const [apiReferences, setApiReferences] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadReferences() {
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE_URL}/api/references`);
        if (res.ok) {
          const data = await res.json();
          if (active && Array.isArray(data)) {
            setApiReferences(data);
          }
        }
      } catch {
        // Fall back to built-in reference specifications from foodItems
      } finally {
        if (active) setLoading(false);
      }
    }
    loadReferences();
    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <div className="welcome">
        <div>
          <small className="eyebrow">RESEARCH EVIDENCE & DATASETS</small>
          <h1>External Food References</h1>
          <p>
            Compatible research datasets and scientific sensor benchmarks used to assist adaptive baseline fusion.
          </p>
        </div>
      </div>

      <div className="reference-grid">
        {foodItems.map((item) => (
          <article className="reference-card" key={item.id}>
            <div className="reference-emoji" style={{ background: item.color || '#fff3cc' }}>
              {item.emoji}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span className="eyebrow">{item.category}</span>
                <span className="badge" style={{ fontSize: '11px', background: '#dbeafe', color: '#1e40af', padding: '2px 8px', borderRadius: '4px' }}>
                  Confidence: {((item.referenceConfidence || 0.6) * 100).toFixed(0)}%
                </span>
              </div>
              <h3 style={{ marginTop: '4px', marginBottom: '6px' }}>{item.name} Reference Profile</h3>
              <p style={{ fontSize: '13px', color: '#4b5563', marginBottom: '8px' }}>{item.note}</p>

              <div style={{ background: '#f9fafb', borderRadius: '6px', padding: '10px', fontSize: '12px', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Database size={13} color="#2563eb" />
                  <b>Source CSV:</b> <code style={{ fontSize: '11px' }}>{item.referenceDataset}</code>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Cpu size={13} color="#059669" />
                  <b>Sample Count:</b> {item.sampleCount ? item.sampleCount.toLocaleString() : 'N/A'} samples
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={13} color="#d97706" />
                  <b>Active Sensor Channels:</b> {item.sensorCoverage ? item.sensorCoverage.join(', ') : 'Standard'}
                </div>
              </div>

              <small style={{ color: '#6b7280', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Leaf size={14} /> Supplementary external baseline · No fabricated RSL labels
              </small>
            </div>
          </article>
        ))}
      </div>

      <div className="info-panel" style={{ marginTop: '24px' }}>
        <Leaf size={24} />
        <div>
          <h2>Reference Data Architecture & Scientific Integrity</h2>
          <p>
            FreshBox AI keeps external research datasets strictly supplementary. Missing sensor channels (such as temperature/humidity in the tomato dataset, or weight in the banana dataset) are <b>never fabricated</b>. Real-time food freshness assessment is driven by live physical ESP32 sensor readings and customer-generated batch baselines.
          </p>
        </div>
      </div>
    </>
  );
}

