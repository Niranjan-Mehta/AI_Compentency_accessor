import React, { useState } from 'react';
import './LoginView.css';
import { useApp } from '../../context/AppContext.jsx';

export function LoginView({ onLoginSuccess }) {
  const { login, loading } = useApp();
  // Default identifier is blank as requested
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [keepSignedIn, setKeepSignedIn] = useState(false);
  const [capsLockOn, setCapsLockOn] = useState(false);

  // Warning & attempts state
  const [hasError, setHasError] = useState(false);
  const [loginError, setLoginError] = useState('');

  // Monitor Caps Lock key
  const handleKeyActivity = (e) => {
    if (e.getModifierState) {
      setCapsLockOn(e.getModifierState('CapsLock'));
    }
  };

  // Submit Handler with Role-Based Authentication
  const handleSignIn = async (e) => {
    e?.preventDefault();

    try {
      const user = await login(identifier.trim(), password, keepSignedIn);
      setHasError(false);
      setLoginError('');
      onLoginSuccess?.(user);
    } catch (error) {
      setHasError(true);
      setLoginError(error.message || 'Unable to sign in. Check your credentials and try again.');
    }
  };

  return (
    <div className="login-split-page">
      {/* Left Brand Panel */}
      <div className="login-left-panel">
        {/* Brand header */}
        <div className="login-brand-header">
          <div className="login-brand-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <span className="login-brand-title">Competency Assessor</span>
        </div>

        {/* Hero Middle */}
        <div className="login-left-hero">
          <h1 className="login-left-headline">
            Show what you have really learned.
          </h1>
          <p className="login-left-subtext">
            Submit your code, answer questions about it, and watch your skills grow task by task.
          </p>

          <div className="login-features-list">
            <div className="login-feature-item">
              <div className="login-feature-icon-circle">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <span>Scored on your own repo</span>
            </div>

            <div className="login-feature-item">
              <div className="login-feature-icon-circle">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <span>Questions about your own code</span>
            </div>

            <div className="login-feature-item">
              <div className="login-feature-icon-circle">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              </div>
              <span>Private, nothing leaves the network</span>
            </div>
          </div>
        </div>

        {/* Bottom Notice */}
        <div className="login-left-footer">
          For internal training use only
        </div>
      </div>

      {/* Right Sign-in Panel */}
      <div className="login-right-panel">
        <div className="login-form-container">
          <h2 className="login-signin-title">Sign in</h2>
          <p className="login-signin-subtitle">
            Use your employee ID or work email. Your role (Trainee, TA or Faculty) is picked up automatically.
          </p>

          {/* Warning / Error Banner matching IMG_20261011_160521_150c5318.jpg */}
          {hasError && (
            <div className="login-warning-banner">
              <div className="login-warning-icon-badge">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0f172a" strokeWidth="2.8">
                  <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <div className="login-warning-content">
                <span className="login-warning-title">
                  Login failed
                </span>
                <span className="login-warning-desc">
                  {loginError}
                </span>
              </div>
            </div>
          )}

          {/* Login Form */}
          <form className="login-form" onSubmit={handleSignIn}>
            {/* Employee ID or work email */}
            <div className="login-form-group">
              <label className="login-label" htmlFor="login-id-input">
                Employee ID or work email
              </label>
              <input
                id="login-id-input"
                type="text"
                className="login-input"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="2345678"
                autoComplete="username"
                required
              />
              <span className="login-helper-text">
                Example: 2345678 or name@company.com
              </span>
            </div>

            {/* Password */}
            <div className="login-form-group">
              <label className="login-label" htmlFor="login-password-input">
                Password
              </label>
              <div className="login-password-wrapper">
                <input
                  id="login-password-input"
                  type={showPassword ? 'text' : 'password'}
                  className="login-password-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={handleKeyActivity}
                  onKeyUp={handleKeyActivity}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="login-password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  <span>{showPassword ? 'Hide' : 'Show'}</span>
                </button>
              </div>

              {/* Caps Lock indicator (always visible if active, or active toggle) */}
              {capsLockOn && (
                <div className="login-caps-warning">
                  <span className="login-caps-icon">ℹ</span>
                  <span>Caps Lock is on</span>
                </div>
              )}
            </div>

            {/* Keep me signed in & Forgot Password */}
            <div className="login-options-row">
              <label className="login-checkbox-label">
                <input
                  type="checkbox"
                  className="login-checkbox"
                  checked={keepSignedIn}
                  onChange={(e) => setKeepSignedIn(e.target.checked)}
                />
                <span>Keep me signed in</span>
              </label>

              <button
                type="button"
                className="login-forgot-link"
                onClick={() => {
                  alert('Password reset is not configured. Contact your system administrator.');
                }}
              >
                Forgot password?
              </button>
            </div>

            {/* Submit button */}
            <button
              type="submit"
              className="login-submit-btn"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          {/* Footer note */}
          <div className="login-trouble-text">
            Trouble signing in? Contact your TA or faculty. They can reset your access.
          </div>
        </div>
      </div>
    </div>
  );
}
