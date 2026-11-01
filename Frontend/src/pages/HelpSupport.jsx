import React from 'react';
import {
  CircleHelp,
  Thermometer,
  Wifi,
  Leaf,
  MessageCircle
} from 'lucide-react';

export default function HelpSupport() {
  return (
    <div className="settings-page">
      <div className="page-heading">
        <div>
          <h1>Help & Support</h1>
          <p>
            Find assistance for your FreshBox AI food freshness system.
          </p>
        </div>
      </div>

      <div className="settings-grid">
        <section className="settings-card">
          <div className="settings-card-title">
            <Thermometer size={22} />
            <div>
              <h3>Sensor Issues</h3>
              <p>
                Learn how to configure temperature, humidity,
                gas response, and weight sensors.
              </p>
            </div>
          </div>
        </section>

        <section className="settings-card">
          <div className="settings-card-title">
            <Wifi size={22} />
            <div>
              <h3>Device Connectivity</h3>
              <p>
                Check your ESP32 connection and device status.
              </p>
            </div>
          </div>
        </section>

        <section className="settings-card">
          <div className="settings-card-title">
            <Leaf size={22} />
            <div>
              <h3>Food Freshness</h3>
              <p>
                Understand freshness levels and estimated
                remaining shelf life.
              </p>
            </div>
          </div>
        </section>

        <section className="settings-card">
          <div className="settings-card-title">
            <MessageCircle size={22} />
            <div>
              <h3>Contact Support</h3>
              <p>
                Get help with your FreshBox application.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}