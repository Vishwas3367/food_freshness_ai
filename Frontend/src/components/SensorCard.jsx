import React from 'react';

export default function SensorCard({
  icon: Icon,
  label,
  value,
  unit,
  caption,
  status = 'demo'
}) {
  return (
    <div className="sensor">
      <div className="sensor-head">
        <div className="sensor-icon"><Icon size={18} /></div>
        <small className={`sensor-state ${status.replace(/\s+/g, '-')}`}>
          ● {status}
        </small>
      </div>
      <label>{label}</label>
      <strong>{value}<span>{unit}</span></strong>
      <p>{caption}</p>
    </div>
  );
}
