
import React from 'react';

import {
  Clock3,
  ArrowUpRight
} from 'lucide-react';

export default function FoodCard({ item, onClick }) {
  // Support both existing sample data and newly added items
  const quantity =
    item.quantityKg !== undefined &&
    item.quantityKg !== null &&
    item.quantityKg !== ''
      ? `${Number(item.quantityKg).toFixed(2)} kg`
      : item.qty || 'Quantity not recorded';

  const score = Number(item.score ?? 100);

  const status =
    item.status ||
    (score >= 70
      ? 'Fresh'
      : score >= 40
      ? 'Use soon'
      : 'Critical');

  const statusClass =
    status === 'Fresh'
      ? 'fresh'
      : status === 'Use soon'
      ? 'soon'
      : 'critical';

  return (
    <button
      type="button"
      className="food-card"
      onClick={() => onClick?.(item)}
    >
      <div
        className="food-picture"
        style={{
          background: item.color || '#f0fdf4'
        }}
      >
        <span>{item.emoji || '🥬'}</span>
      </div>

      <div className="food-info">
        <div className="food-title">
          <div>
            <b>{item.name}</b>

            <small>
              {item.category} · {quantity}
            </small>
          </div>

          <span className={`status ${statusClass}`}>
            {status}
          </span>
        </div>

        <div className="fresh-row">
          <span>Freshness level</span>

          <b>{score}%</b>
        </div>

        <div className="track">
          <div
            className="fill"
            style={{
              width: `${Math.max(0, Math.min(100, score))}%`
            }}
          />
        </div>

        <div className="food-bottom">
          <span>
            <Clock3 size={13} />

            Estimated {item.days ?? '—'} days left
          </span>

          <ArrowUpRight size={16} />
        </div>
      </div>
    </button>
  );
}
