
import React from 'react';

import {
  LayoutDashboard,
  Boxes,
  Activity,
  TrendingUp,
  Leaf,
  Settings,
  CircleHelp
} from 'lucide-react';

const links = [
  ['Dashboard', LayoutDashboard],
  ['Food Inventory', Boxes],
  ['Live Monitoring', Activity],
  ['AI Predictions', TrendingUp],
  ['Food Reference', Leaf]
];

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="sidebar">

      {/* Brand */}
      <div className="brand">
        <div className="brandmark">🍃</div>

        <div>
          <b>
            FreshBox <span>AI</span>
          </b>

          <small>SMART FOOD SYSTEM</small>
        </div>
      </div>

      {/* Main Navigation */}
      <p className="nav-label">WORKSPACE</p>

      {links.map(([name, Icon]) => (
        <button
          type="button"
          key={name}
          className={
            'navlink ' +
            (active === name ? 'active' : '')
          }
          onClick={() => onNavigate(name)}
        >
          <Icon size={18} />

          {name}

          {name === 'Food Inventory' && (
            <em>6</em>
          )}
        </button>
      ))}

      {/* Bottom Navigation */}
      <div className="sidebar-end">

        {/* Device Status */}
        <div className="device">
          <span>● Box connected</span>

          <b>FreshBox #FB-001</b>

          <small>ESP32 device · Online</small>
        </div>

        {/* Settings Button */}
        <button
          type="button"
          className={
            'navlink ' +
            (active === 'Settings' ? 'active' : '')
          }
          onClick={() => onNavigate('Settings')}
        >
          <Settings size={18} />

          Settings
        </button>

        {/* Help & Support Button */}
        <button
          type="button"
          className={
            'navlink ' +
            (active === 'Help & support' ? 'active' : '')
          }
          onClick={() => onNavigate('Help & support')}
        >
          <CircleHelp size={18} />

          Help & support
        </button>

      </div>
    </aside>
  );
}
