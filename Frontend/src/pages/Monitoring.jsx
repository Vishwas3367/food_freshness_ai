import React, { useEffect, useState } from 'react';
import {
  Activity,
  Droplets,
  Thermometer,
  Weight,
  Wind
} from 'lucide-react';
import SensorCard from '../components/SensorCard.jsx';

const API_BASE_URL = (
  import.meta.env.VITE_FRESHBOX_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');
const REFRESH_INTERVAL_MS = 2000;

async function fetchJson(url) {
  const response = await fetch(url);
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      body?.detail || `API request failed with HTTP ${response.status}.`
    );
  }

  return body;
}

function formatValue(value, digits = 1) {
  return value === null || value === undefined || !Number.isFinite(Number(value))
    ? '--'
    : Number(value).toFixed(digits);
}

function sensorState(reading, validity, field) {
  if (!reading) return 'no data';
  return validity?.[field] && reading[field] !== null ? 'valid' : 'unavailable';
}

export default function Monitoring() {
  const [batches, setBatches] = useState([]);
  const [batchId, setBatchId] = useState('');
  const [latest, setLatest] = useState(null);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [readingLoading, setReadingLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    async function loadBatches() {
      try {
        const result = await fetchJson(`${API_BASE_URL}/api/batches`);
        if (!active) return;

        const availableBatches = Array.isArray(result) ? result : [];
        setBatches(availableBatches);
        setBatchId((currentId) => {
          return availableBatches.some((batch) => batch.batch_id === currentId)
            ? currentId
            : availableBatches[0]?.batch_id || '';
        });
        setError('');
      } catch (requestError) {
        if (active) {
          setError(`Could not load batches: ${requestError.message}`);
        }
      } finally {
        if (active) setBatchesLoading(false);
      }
    }

    loadBatches();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!batchId) {
      setLatest(null);
      return undefined;
    }

    let active = true;
    let timeoutId;

    async function loadLatest() {
      setReadingLoading(true);
      try {
        const result = await fetchJson(
          `${API_BASE_URL}/api/sensors/latest?batch_id=${encodeURIComponent(batchId)}`
        );
        if (active) {
          setLatest(result);
          setError('');
        }
      } catch (requestError) {
        if (active) {
          setError(`Could not load sensor readings: ${requestError.message}`);
        }
      } finally {
        if (active) {
          setReadingLoading(false);
          timeoutId = window.setTimeout(loadLatest, REFRESH_INTERVAL_MS);
        }
      }
    }

    loadLatest();
    return () => {
      active = false;
      window.clearTimeout(timeoutId);
    };
  }, [batchId]);

  const reading = latest?.reading;
  const validity = reading?.sensor_validity_json || {};
  const deviceStatus = latest?.device_status || 'offline';
  const selectedBatch = batches.find((batch) => batch.batch_id === batchId);
  const readingTime = reading?.timestamp
    ? new Date(reading.timestamp).toLocaleString()
    : null;

  return (
    <>
      <div className="welcome">
        <div>
          <small className="eyebrow">SENSOR TELEMETRY</small>
          <h1>Live Monitoring</h1>
          <p>Live readings reported by your ESP32 FreshBox device.</p>
        </div>
        <span className={`connection-badge ${deviceStatus}`}>
          <Activity size={13} />
          {deviceStatus}
        </span>
      </div>

      <section className="monitor-toolbar">
        <label htmlFor="monitor-batch">Food batch</label>
        <select
          id="monitor-batch"
          value={batchId}
          disabled={batchesLoading || batches.length === 0}
          onChange={(event) => setBatchId(event.target.value)}
        >
          {batches.length === 0 && <option value="">No batches found</option>}
          {batches.map((batch) => (
            <option key={batch.batch_id} value={batch.batch_id}>
              {batch.name || batch.food_name} ({batch.status})
            </option>
          ))}
        </select>
        <span>
          {selectedBatch
            ? `${selectedBatch.food_name} · ${selectedBatch.batch_id}`
            : batchesLoading
              ? 'Loading batches…'
              : 'Create a food batch in the API to begin.'}
        </span>
      </section>

      {error && <div className="monitor-error" role="alert">{error}</div>}

      <div className="sensor-grid">
        <SensorCard
          icon={Thermometer}
          label="Temperature"
          value={formatValue(reading?.temperature_c)}
          unit="°C"
          caption="DHT22"
          status={sensorState(reading, validity, 'temperature')}
        />
        <SensorCard
          icon={Droplets}
          label="Humidity"
          value={formatValue(reading?.humidity_pct)}
          unit="%"
          caption="DHT22"
          status={sensorState(reading, validity, 'humidity')}
        />
        <SensorCard
          icon={Wind}
          label="Gas response"
          value={formatValue(reading?.gas_raw, 0)}
          unit="raw"
          caption="MQ-135 ADC; not calibrated ppm"
          status={sensorState(reading, validity, 'gas_raw')}
        />
        <SensorCard
          icon={Weight}
          label="Weight"
          value={formatValue(reading?.weight_g)}
          unit="g"
          caption="HX711 load cell"
          status={sensorState(reading, validity, 'weight')}
        />
      </div>

      <section className="info-panel monitor-status-panel">
        <Activity size={18} />
        <div>
          <h2>
            {reading
              ? `Device ${reading.device_id} · ${deviceStatus}`
              : 'Waiting for sensor data'}
          </h2>
          <p>
            {readingTime
              ? `Last reading: ${readingTime}${latest.latest_reading_age_seconds !== undefined ? ` · ${latest.latest_reading_age_seconds}s ago` : ''}. Refreshes automatically every 10 seconds.`
              : readingLoading
                ? 'Connecting to the FreshBox API…'
                : 'No reading has been recorded for this batch yet. Confirm the ESP32 is online and sending data to the API.'}
          </p>
        </div>
      </section>
    </>
  );
}
