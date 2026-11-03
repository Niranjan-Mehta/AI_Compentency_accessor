import React from 'react';
import './Header.css';
import { useApp } from '../../context/AppContext.jsx';

export const Header = ({ currentView, onNavigate, onLogout }) => {
  const { currentUser, refreshWorkspace } = useApp();

  return (
    <header className="top-header">
      <div className="header-left">
        <div 
          className="brand-logo" 
          onClick={() => onNavigate('dashboard')}
          role="button"
          tabIndex={0}
        >
          <div className="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <span className="brand-name">Competency Assessor</span>
        </div>

        <nav className="nav-tabs">
          <button 
            className={`nav-tab-btn ${currentView === 'dashboard' || currentView === 'submit-work' || currentView === 'code-questions' ? 'active' : ''}`}
            onClick={() => onNavigate('dashboard')}
          >
            Dashboard
          </button>
          
          <button 
            className={`nav-tab-btn ${currentView === 'report-detail' ? 'active' : ''}`}
            onClick={() => onNavigate('report-detail')}
          >
            My reports
          </button>

          <button 
            className="nav-tab-btn"
            onClick={() => alert('Help desk contact information is not configured. Please contact your faculty.')}
          >
            Help
          </button>
        </nav>
      </div>

      <div className="header-right">

        <div className="user-info">
          <div className="user-name">{currentUser.fullName}</div>
          <div className="user-role">{currentUser.roleLabel || currentUser.role}</div>
        </div>

        <div className="avatar-badge" title={currentUser.fullName}>
          {currentUser.avatar}
        </div>

        <button 
          className="logout-btn" 
          title="Sign out"
          onClick={() => {
            if (onLogout) {
              onLogout();
            } else {
              onNavigate('login');
            }
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
        </button>
      </div>
    </header>
  );
};
