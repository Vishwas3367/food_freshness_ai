
import React, { useState } from 'react';

import {
  Thermometer,
  Droplets,
  Wind,
  Scale,
  Bell,
  Save,
  RotateCcw,
  Settings as SettingsIcon
} from 'lucide-react';

const DEFAULT_SETTINGS = {
  temperature: 8,
  humidity: 70,
  gasThreshold: 300,
  weightAlert: 100,
  freshnessAlerts: true,
  temperatureAlerts: true,
  humidityAlerts: true
};

export default function Settings() {
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('freshbox-settings');

      return saved
        ? {
            ...DEFAULT_SETTINGS,
            ...JSON.parse(saved)
          }
        : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  const [saved, setSaved] = useState(false);

  // Update a setting
  const updateSetting = (key, value) => {
    setSettings((previous) => ({
      ...previous,
      [key]: value
    }));

    setSaved(false);
  };

  // Save settings in browser storage
  const handleSave = () => {
    try {
      localStorage.setItem(
        'freshbox-settings',
        JSON.stringify(settings)
      );

      setSaved(true);
    } catch {
      alert('Unable to save settings. Please try again.');
    }
  };

  // Restore default settings
  const handleReset = () => {
    setSettings({ ...DEFAULT_SETTINGS });
    setSaved(false);
  };

  return (
    <div className="settings-page">

      {/* Page Heading */}
      <div className="page-heading">
        <div>
          <h1>Settings</h1>

          <p>
            Configure your FreshBox device and notification preferences.
          </p>
        </div>
      </div>

      {/* Settings Cards */}
      <div className="settings-grid">

        {/* Temperature */}
        <section className="settings-card">
          <div className="settings-card-title">
            <Thermometer size={20} />

            <div>
              <h3>Temperature Threshold</h3>

              <p>
                Set the maximum acceptable box temperature.
              </p>
            </div>
          </div>

          <label>
            Maximum temperature (°C)

            <input
              type="number"
              min="-10"
              max="50"
              value={settings.temperature}
              onChange={(e) =>
                updateSetting(
                  'temperature',
                  Number(e.target.value)
                )
              }
            />
          </label>
        </section>

        {/* Humidity */}
        <section className="settings-card">
          <div className="settings-card-title">
            <Droplets size={20} />

            <div>
              <h3>Humidity Threshold</h3>

              <p>
                Set the maximum humidity level.
              </p>
            </div>
          </div>

          <label>
            Maximum humidity (%)

            <input
              type="number"
              min="0"
              max="100"
              value={settings.humidity}
              onChange={(e) =>
                updateSetting(
                  'humidity',
                  Number(e.target.value)
                )
              }
            />
          </label>
        </section>

        {/* Gas Sensor */}
        <section className="settings-card">
          <div className="settings-card-title">
            <Wind size={20} />

            <div>
              <h3>Gas Sensor (MQ-135)</h3>

              <p>
                Configure the gas-response alert threshold.
              </p>
            </div>
          </div>

          <label>
            Gas response threshold

            <input
              type="number"
              min="0"
              value={settings.gasThreshold}
              onChange={(e) =>
                updateSetting(
                  'gasThreshold',
                  Number(e.target.value)
                )
              }
            />
          </label>

          <small className="settings-note">
            The MQ-135 provides a broad gas-response signal.
            This threshold is illustrative and requires calibration.
          </small>
        </section>

        {/* Weight Sensor */}
        <section className="settings-card">
          <div className="settings-card-title">
            <Scale size={20} />

            <div>
              <h3>Weight Sensor (HX711)</h3>

              <p>
                Set a low-weight notification threshold.
              </p>
            </div>
          </div>

          <label>
            Minimum weight (g)

            <input
              type="number"
              min="0"
              value={settings.weightAlert}
              onChange={(e) =>
                updateSetting(
                  'weightAlert',
                  Number(e.target.value)
                )
              }
            />
          </label>
        </section>

        {/* Notifications */}
        <section className="settings-card notification-card">
          <div className="settings-card-title">
            <Bell size={20} />

            <div>
              <h3>Notifications</h3>

              <p>
                Choose which alerts you want to receive.
              </p>
            </div>
          </div>

          {/* Freshness Alerts */}
          <label className="toggle-row">
            <span>
              <b>Freshness alerts</b>

              <small>
                Notify when food freshness decreases.
              </small>
            </span>

            <input
              type="checkbox"
              checked={settings.freshnessAlerts}
              onChange={(e) =>
                updateSetting(
                  'freshnessAlerts',
                  e.target.checked
                )
              }
            />
          </label>

          {/* Temperature Alerts */}
          <label className="toggle-row">
            <span>
              <b>Temperature alerts</b>

              <small>
                Notify when temperature exceeds the threshold.
              </small>
            </span>

            <input
              type="checkbox"
              checked={settings.temperatureAlerts}
              onChange={(e) =>
                updateSetting(
                  'temperatureAlerts',
                  e.target.checked
                )
              }
            />
          </label>

          {/* Humidity Alerts */}
          <label className="toggle-row">
            <span>
              <b>Humidity alerts</b>

              <small>
                Notify when humidity exceeds the threshold.
              </small>
            </span>

            <input
              type="checkbox"
              checked={settings.humidityAlerts}
              onChange={(e) =>
                updateSetting(
                  'humidityAlerts',
                  e.target.checked
                )
              }
            />
          </label>
        </section>

      </div>

      {/* Action Buttons */}
      <div className="settings-actions">

        <button
          type="button"
          className="save-settings-btn"
          onClick={handleSave}
        >
          <Save size={18} />
          Save Settings
        </button>

        <button
          type="button"
          className="reset-settings-btn"
          onClick={handleReset}
        >
          <RotateCcw size={18} />
          Reset
        </button>

        {saved && (
          <span className="settings-success">
            Settings saved successfully!
          </span>
        )}

      </div>

    </div>
  );
}
