import React from 'react';
import './AdminHeader.css';
import { useApp } from '../../context/AppContext.jsx';

export const AdminHeader = ({ activeTab, onSelectTab, onLogout, role = 'FACULTY' }) => {
  const { currentUser } = useApp();
  const fullName = currentUser?.fullName || currentUser?.username || '';
  const roleLabel = role === 'TA' ? 'Teaching assistant' : 'Faculty';
  return (
    <header className="admin-header">
      <div className="admin-header-left">
        <div 
          className="admin-brand-logo" 
          onClick={() => onSelectTab('overview')}
          role="button"
          tabIndex={0}
        >
          <div className="admin-brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <span className="admin-brand-name">Competency Assessor</span>
        </div>

        <nav className="admin-nav-tabs">
          {role === 'TA' ? (
            <button className={`admin-nav-tab-btn ${activeTab === 'review' ? 'active' : ''}`} onClick={() => onSelectTab('review')}>
              Assessments
            </button>
          ) : (
            <>
          <button 
            className={`admin-nav-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => onSelectTab('overview')}
          >
            Overview
          </button>
          
          <button 
            className={`admin-nav-tab-btn ${activeTab === 'batches' ? 'active' : ''}`}
            onClick={() => onSelectTab('batches')}
          >
            Batches
          </button>

          <button 
            className={`admin-nav-tab-btn ${activeTab === 'rubrics' ? 'active' : ''}`}
            onClick={() => onSelectTab('rubrics')}
          >
            Rubrics
          </button>

          <button 
            className={`admin-nav-tab-btn ${activeTab === 'reports' ? 'active' : ''}`}
            onClick={() => onSelectTab('reports')}
          >
            Reports
          </button>

          <button 
            className={`admin-nav-tab-btn ${activeTab === 'audit-log' ? 'active' : ''}`}
            onClick={() => onSelectTab('audit-log')}
          >
            Audit log
          </button>
            </>
          )}
        </nav>
      </div>

      <div className="admin-header-right">
        <div className="admin-user-info">
          <div className="admin-user-name">{fullName}</div>
          <div className="admin-user-role">{roleLabel}</div>
        </div>

        <div className="admin-avatar-badge" title={fullName}>
          {currentUser?.avatar}
        </div>

        <button 
          className="admin-logout-btn" 
          title="Sign out of Admin"
          onClick={onLogout}
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
