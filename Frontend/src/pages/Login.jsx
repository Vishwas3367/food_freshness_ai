
import React, { useState } from 'react';

import {
  Leaf,
  Mail,
  Lock,
  LogIn,
  Eye,
  EyeOff,
  ShieldCheck,
  Thermometer,
  Droplets,
  Activity
} from 'lucide-react';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!email.trim() || !password.trim()) {
      setError('Please enter your email and password.');
      return;
    }

    setError('');

    // Demo login: accepts non-empty email and password.
    onLogin({
      name: email.split('@')[0],
      email
    });
  };

  return (
    <div className="login-page">

      {/* Left showcase panel */}
      <section className="login-showcase">

        <div className="showcase-background-shape shape-one" />
        <div className="showcase-background-shape shape-two" />

        {/* Brand */}
        <div className="showcase-brand">
          <div className="showcase-brand-icon">
            <Leaf size={23} />
          </div>

          <div>
            <h2>
              FreshBox <span>AI</span>
            </h2>

            <p>SMART FOOD SYSTEM</p>
          </div>
        </div>

        {/* Showcase heading */}
        <div className="showcase-content">
          <span className="showcase-eyebrow">
            SMARTER FOOD STORAGE
          </span>

          <h1>
            Freshness,
            <br />
            <span>at a glance.</span>
          </h1>

          <p>
            Your food. Your freshness.
            <br />
            Your peace of mind.
          </p>
        </div>

        {/* Freshness visual */}
        <div className="freshness-visual">

          <div className="freshness-glow" />

          <div className="freshness-orbit orbit-one" />
          <div className="freshness-orbit orbit-two" />

          <div className="freshness-box">

            <div className="freshness-box-top">
              <div className="box-brand">
                <Leaf size={14} />
                FreshBox AI
              </div>

              <div className="box-sensor-light" />
            </div>

            <div className="freshness-produce">
              <span className="produce-emoji">🥬</span>
              <span className="produce-emoji">🍎</span>
              <span className="produce-emoji">🍅</span>
              <span className="produce-emoji">🥑</span>
              <span className="produce-emoji">🥕</span>
            </div>

            <div className="freshness-box-base" />
          </div>

          {/* Floating sensor cards */}
          <div className="sensor-float sensor-temperature">
            <div className="sensor-float-icon">
              <Thermometer size={18} />
            </div>

            <div>
              <small>Temperature</small>
              <b>4.2°C</b>
            </div>
          </div>

          <div className="sensor-float sensor-humidity">
            <div className="sensor-float-icon">
              <Droplets size={18} />
            </div>

            <div>
              <small>Humidity</small>
              <b>68%</b>
            </div>
          </div>

          <div className="sensor-float sensor-freshness">
            <div className="freshness-status-dot" />

            <div>
              <small>Food condition</small>
              <b>Fresh</b>
            </div>
          </div>

        </div>

        {/* Bottom features */}
        <div className="showcase-features">

          <div className="showcase-feature">
            <Leaf size={21} />
            <span>Monitor freshness</span>
          </div>

          <div className="showcase-feature">
            <ShieldCheck size={21} />
            <span>Reduce food waste</span>
          </div>

          <div className="showcase-feature">
            <Activity size={21} />
            <span>AI-powered insights</span>
          </div>

        </div>

      </section>

      {/* Right login panel */}
      <section className="login-form-panel">

        <div className="login-card">

          {/* Login brand */}
          <div className="login-brand">
            <div className="login-brand-icon">
              <Leaf size={27} />
            </div>

            <div>
              <h2>
                FreshBox <span>AI</span>
              </h2>

              <p>SMART FOOD SYSTEM</p>
            </div>
          </div>

          {/* Heading */}
          <div className="login-heading">
            <span className="login-welcome-label">
              WELCOME BACK
            </span>

            <h1>Welcome back!</h1>

            <p>
              Sign in to access your FreshBox dashboard.
            </p>
          </div>

          {/* Login form */}
          <form onSubmit={handleSubmit}>

            <label htmlFor="email">
              Email address
            </label>

            <div className="login-input">
              <Mail size={18} />

              <input
                id="email"
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>

            <label htmlFor="password">
              Password
            </label>

            <div className="login-input">
              <Lock size={18} />

              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowPassword((previous) => !previous)
                }
                aria-label={
                  showPassword
                    ? 'Hide password'
                    : 'Show password'
                }
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>

            {error && (
              <p className="login-error">
                {error}
              </p>
            )}

            <button
              type="submit"
              className="login-submit"
            >
              <LogIn size={19} />
              Login to Dashboard
            </button>

          </form>

          {/* Security note */}
          <div className="login-security">
            <ShieldCheck size={17} />

            <span>
              Secure access to your FreshBox workspace
            </span>
          </div>

        </div>

        <div className="login-panel-footer">
          <span>FreshBox AI</span>
          <span>Smart Food Freshness Monitoring</span>
        </div>

      </section>

    </div>
  );
}
