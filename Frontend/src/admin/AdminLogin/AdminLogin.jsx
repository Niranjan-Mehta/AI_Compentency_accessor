import React, { useState } from 'react';
import './AdminLogin.css';

export const AdminLogin = ({ onLoginSuccess, onCancel }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = (e) => {
    e.preventDefault();
    if (username.trim() === 'admin' && password === 'admin@123') {
      setError('');
      onLoginSuccess();
    } else {
      setError('Invalid username or password. Default is admin / admin@123');
    }
  };

  const handleQuickFill = () => {
    setUsername('admin');
    setPassword('admin@123');
    setError('');
  };

  return (
    <div className="admin-login-wrapper">
      <div className="admin-login-card">
        <div className="admin-login-header">
          <div className="admin-login-brand-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <h2 className="admin-login-title">Faculty & Admin Portal</h2>
          <p className="admin-login-subtitle">Sign in to manage batches, rubrics, and dispute reviews</p>
        </div>

        <div className="admin-login-credentials-banner">
          <div className="admin-login-credentials-text">
            Default credentials:<br />
            Username: <strong>admin</strong> | Password: <strong>admin@123</strong>
          </div>
          <button 
            type="button" 
            className="admin-btn-quickfill"
            onClick={handleQuickFill}
          >
            Auto-fill
          </button>
        </div>

        {error && (
          <div className="admin-login-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="admin-login-form">
          <div className="admin-login-field-group">
            <label className="admin-login-label" htmlFor="admin-username-input">
              Username
            </label>
            <input 
              id="admin-username-input"
              type="text"
              className="admin-login-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. admin"
              autoFocus
              required
            />
          </div>

          <div className="admin-login-field-group">
            <label className="admin-login-label" htmlFor="admin-password-input">
              Password
            </label>
            <input 
              id="admin-password-input"
              type="password"
              className="admin-login-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" className="admin-login-submit-btn">
            Sign In as Admin
          </button>
        </form>

        <div className="admin-login-footer">
          <button 
            type="button" 
            className="admin-btn-back-trainee"
            onClick={onCancel}
          >
            ← Return to Trainee Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};
