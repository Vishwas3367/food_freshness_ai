
import React, { useEffect, useState } from 'react';

import {
  Thermometer,
  Droplets,
  Wind,
  Weight,
  ArrowUpRight,
  Plus,
  X
} from 'lucide-react';

import SensorCard from '../components/SensorCard.jsx';
import FoodCard from '../components/FoodCard.jsx';

const API_BASE_URL = (
  import.meta.env.VITE_FRESHBOX_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');
const SENSOR_REFRESH_INTERVAL_MS = 2000;

async function fetchLatestSensorReading() {
  const batchesResponse = await fetch(`${API_BASE_URL}/api/batches`);
  if (!batchesResponse.ok) {
    throw new Error(`Could not load batches (HTTP ${batchesResponse.status}).`);
  }
  const batches = await batchesResponse.json();
  // Find the active ESP32 live batch, or first batch
  const batch = batches.find((b) => b.batch_id === '74845293-ee42-4778-baad-1336c0331798') || batches[0];
  if (!batch) return null;

  const readingResponse = await fetch(
    `${API_BASE_URL}/api/sensors/latest?batch_id=${encodeURIComponent(batch.batch_id)}`
  );
  if (!readingResponse.ok) {
    throw new Error(`Could not load sensor data (HTTP ${readingResponse.status}).`);
  }

  return {
    batch,
    ...await readingResponse.json()
  };
}

function displayReading(value, digits = 1) {
  return value === null || value === undefined || !Number.isFinite(Number(value))
    ? '--'
    : Number(value).toFixed(digits);
}

export default function Dashboard({
  items = [],
  onSelect,
  onAll,
  onAddFood
}) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  const [telemetryError, setTelemetryError] = useState('');

  useEffect(() => {
    let active = true;
    let timeoutId;

    async function refreshTelemetry() {
      try {
        const latest = await fetchLatestSensorReading();
        if (active) {
          setTelemetry(latest);
          setTelemetryError('');
        }
      } catch (error) {
        if (active) setTelemetryError(error.message);
      } finally {
        if (active) {
          timeoutId = window.setTimeout(
            refreshTelemetry,
            SENSOR_REFRESH_INTERVAL_MS
          );
        }
      }
    }

    refreshTelemetry();
    return () => {
      active = false;
      window.clearTimeout(timeoutId);
    };
  }, []);

  const getGreeting = () => {
    const hour = new Date().getHours();

    if (hour >= 5 && hour < 12) {
      return { text: 'Good morning', emoji: '☀️' };
    }

    if (hour >= 12 && hour < 17) {
      return { text: 'Good afternoon', emoji: '👋' };
    }

    if (hour >= 17 && hour < 21) {
      return { text: 'Good evening', emoji: '🌆' };
    }

    return { text: 'Good night', emoji: '🌙' };
  };

  const greeting = getGreeting();

  // Current local date and time for the form
  const getLocalDateTime = () => {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;

    return new Date(now.getTime() - offset)
      .toISOString()
      .slice(0, 16);
  };

  const [foodSourceMode, setFoodSourceMode] = useState('Banana'); // 'Banana' | 'Tomato' | 'custom'

  const [formData, setFormData] = useState({
    name: 'Banana',
    category: 'Fruit',
    quantityKg: '1.00',
    addedAt: getLocalDateTime(),
    notes: ''
  });

  const handleSelectProduceMode = (mode) => {
    setFoodSourceMode(mode);
    if (mode === 'Banana') {
      setFormData((prev) => ({
        ...prev,
        name: 'Banana',
        category: 'Fruit',
        emoji: '🍌',
        color: '#fff3cc'
      }));
    } else if (mode === 'Tomato') {
      setFormData((prev) => ({
        ...prev,
        name: 'Tomato',
        category: 'Vegetable',
        emoji: '🍅',
        color: '#ffe5e1'
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        name: '',
        category: 'Fruit',
        emoji: '🥗',
        color: '#eaf4e8'
      }));
    }
  };

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((previous) => ({
      ...previous,
      [name]: value
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    if (!formData.name.trim()) {
      alert('Please enter or select a food name.');
      return;
    }

    if (
      formData.quantityKg === '' ||
      Number(formData.quantityKg) <= 0
    ) {
      alert('Please enter a valid quantity in kg.');
      return;
    }

    if (!formData.addedAt) {
      alert('Please select the date and time added.');
      return;
    }

    const emoji =
      formData.name.toLowerCase() === 'banana'
        ? '🍌'
        : formData.name.toLowerCase() === 'tomato'
        ? '🍅'
        : formData.category === 'Vegetable'
        ? '🥦'
        : '🍎';

    const color =
      formData.name.toLowerCase() === 'banana'
        ? '#fff3cc'
        : formData.name.toLowerCase() === 'tomato'
        ? '#ffe5e1'
        : '#eaf4e8';

    // Send the new item to App.jsx
    onAddFood?.({
      name: formData.name.trim(),
      category: formData.category,
      quantityKg: Number(formData.quantityKg),
      addedAt: new Date(formData.addedAt).toISOString(),
      notes: formData.notes.trim(),
      emoji,
      color,
      isExternalReference:
        formData.name.toLowerCase() === 'banana' ||
        formData.name.toLowerCase() === 'tomato'
    });

    // Reset the form
    setFormData({
      name: 'Banana',
      category: 'Fruit',
      quantityKg: '1.00',
      addedAt: getLocalDateTime(),
      notes: ''
    });
    setFoodSourceMode('Banana');

    setShowAddForm(false);
  };

  return (
    <>
      {/* Welcome Section */}
      <div className="welcome">
        <div>
          <small className="eyebrow">
            SMART FOOD FRESHNESS SYSTEM
          </small>

          <h1>
            {greeting.text} {greeting.emoji}
          </h1>

          <p>
            Here's what's happening inside your FreshBox today.
          </p>
        </div>
      </div>

      {/* Box Overview */}
      <div className="section-head">
        <div>
          <h2>Box overview</h2>

          <p>
            {telemetry?.reading
              ? `Live readings from ${telemetry.batch.food_name || telemetry.batch.name || 'your batch'}.`
              : 'Live sensor readings appear here when the API receives device data.'}
          </p>
        </div>
        <span className={`connection-badge ${telemetry?.device_status || 'offline'}`}>
          {telemetry?.device_status || 'offline'}
        </span>
      </div>

      <div className="sensor-grid">
        <SensorCard
          icon={Thermometer}
          label="Temperature"
          value={displayReading(telemetry?.reading?.temperature_c)}
          unit="°C"
          caption="DHT22 · live"
          status={telemetry?.reading?.sensor_validity_json?.temperature ? 'valid' : 'unavailable'}
        />

        <SensorCard
          icon={Droplets}
          label="Humidity"
          value={displayReading(telemetry?.reading?.humidity_pct)}
          unit="%"
          caption="DHT22 · live"
          status={telemetry?.reading?.sensor_validity_json?.humidity ? 'valid' : 'unavailable'}
        />

        <SensorCard
          icon={Wind}
          label="Gas response"
          value={displayReading(telemetry?.reading?.gas_raw, 0)}
          unit="raw"
          caption="MQ-135 ADC · not ppm"
          status={telemetry?.reading?.sensor_validity_json?.gas_raw ? 'valid' : 'unavailable'}
        />

        <SensorCard
          icon={Weight}
          label="Measured weight"
          value={displayReading(telemetry?.reading?.weight_g)}
          unit="g"
          caption="HX711 · live"
          status={telemetry?.reading?.sensor_validity_json?.weight ? 'valid' : 'unavailable'}
        />
      </div>
      {telemetryError && (
        <div className="monitor-error" role="status">
          Sensor API unavailable: {telemetryError}
        </div>
      )}

      {/* Food Inventory Preview */}
      <div className="section-head section-space">
        <div>
          <h2>Food inventory preview</h2>

          <p>
            Quick look at fruits and vegetables stored in your box.
          </p>
        </div>

        <button
          className="text-button"
          onClick={onAll}
        >
          Open inventory
          <ArrowUpRight size={16} />
        </button>
      </div>

      <div className="food-grid">
        {items.slice(0, 3).map((item) => (
          <FoodCard
            key={item.id}
            item={item}
            onClick={onSelect}
          />
        ))}
      </div>

      {/* Add Food Section */}
      <div className="add-food-section">
        <div className="section-head">
          <div>
            <h2>Add food to FreshBox</h2>

            <p>
              Record the food item, its quantity, and when it was added.
            </p>
          </div>

          <button
            className="add-food-button"
            onClick={() => setShowAddForm((previous) => !previous)}
          >
            {showAddForm ? <X size={17} /> : <Plus size={17} />}

            {showAddForm ? 'Close form' : 'Add food'}
          </button>
        </div>

        {showAddForm && (
          <form
            className="add-food-form"
            onSubmit={handleSubmit}
          >
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Select Produce Baseline:
              </label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid #d1d5db',
                    background: foodSourceMode === 'Banana' ? '#fef08a' : '#fff',
                    fontWeight: foodSourceMode === 'Banana' ? '600' : 'normal',
                    cursor: 'pointer'
                  }}
                  onClick={() => handleSelectProduceMode('Banana')}
                >
                  🍌 Banana (External Research Reference)
                </button>
                <button
                  type="button"
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid #d1d5db',
                    background: foodSourceMode === 'Tomato' ? '#fecaca' : '#fff',
                    fontWeight: foodSourceMode === 'Tomato' ? '600' : 'normal',
                    cursor: 'pointer'
                  }}
                  onClick={() => handleSelectProduceMode('Tomato')}
                >
                  🍅 Tomato (External Research Reference)
                </button>
                <button
                  type="button"
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: '1px solid #d1d5db',
                    background: foodSourceMode === 'custom' ? '#e0e7ff' : '#fff',
                    fontWeight: foodSourceMode === 'custom' ? '600' : 'normal',
                    cursor: 'pointer'
                  }}
                  onClick={() => handleSelectProduceMode('custom')}
                >
                  ➕ Other Produce (Customer-Generated Dataset)
                </button>
              </div>
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="food-name">
                  Food name
                </label>

                <input
                  id="food-name"
                  name="name"
                  type="text"
                  placeholder="e.g. Banana, Tomato, Apple..."
                  value={formData.name}
                  onChange={handleChange}
                  readOnly={foodSourceMode !== 'custom'}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="food-category">
                  Category
                </label>

                <select
                  id="food-category"
                  name="category"
                  value={formData.category}
                  onChange={handleChange}
                  disabled={foodSourceMode !== 'custom'}
                >
                  <option value="Fruit">Fruit</option>
                  <option value="Vegetable">Vegetable</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="food-quantity">
                  Quantity (kg)
                </label>

                <input
                  id="food-quantity"
                  name="quantityKg"
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder="e.g. 1.5"
                  value={formData.quantityKg}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="food-added-at">
                  Date and time added
                </label>

                <input
                  id="food-added-at"
                  name="addedAt"
                  type="datetime-local"
                  value={formData.addedAt}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group form-group-full">
                <label htmlFor="food-notes">
                  Notes (optional)
                </label>

                <textarea
                  id="food-notes"
                  name="notes"
                  placeholder="Add any details about this food..."
                  value={formData.notes}
                  onChange={handleChange}
                  rows="3"
                />
              </div>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="cancel-button"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="add-food-button"
              >
                <Plus size={17} />
                Save food
              </button>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
