import React, { useState, useMemo, useEffect } from 'react';
import './AdminAuditLogView.css';
import { useApp } from '../../context/AppContext.jsx';

export function AdminAuditLogView({ onNavigateTab }) {
  const { api, batches, setAppError } = useApp();
  const [allAuditEntries, setAllAuditEntries] = useState([]);
  useEffect(() => { api.all('/audit-events/').then((events) => setAllAuditEntries(events.map((event) => { const actionLabel = event.action.replaceAll('-', ' ').replace(/\b\w/g, (c) => c.toUpperCase()); const when = new Date(event.created_at); return { id: event.id, whenDate: when.toLocaleDateString(), whenTime: when.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}), whoName: event.actor_name, whoRole: event.actor_role, actionType: event.action, actionLabel, target: event.target || '—', change: JSON.stringify(event.details || {}), batch: batches.find((b) => b.id === event.batch_id)?.name || '—', details: { ...event.details, entryId: `event-${event.id}`, triggeredBy: 'Backend audit log' } }; }))).catch((error) => setAppError(error.message)); }, [api, batches, setAppError]);
  // Filter States - all text boxes start blank as requested
  const [searchQuery, setSearchQuery] = useState('');
  const [whoFilter, setWhoFilter] = useState('Everyone');
  const [actionFilter, setActionFilter] = useState('All');
  const [batchFilter, setBatchFilter] = useState('All 3');
  const [dateFilter, setDateFilter] = useState('Last 7 days');

  // Track expanded rows (Row 1 expanded by default per ad6_9c734827.jpeg)
  const [expandedRows, setExpandedRows] = useState({ 'aud-1': true });
  /*
    {
      id: 'aud-1',
      whenDate: 'Today',
      whenTime: '10:42 am',
      whoName: 'Dr. Meera Iyer',
      whoRole: 'Faculty',
      actionType: 'score-changed',
      actionLabel: 'Score changed',
      target: 'Ravi Kumar, Ticket API with DRF',
      change: 'Security 2 / 5 to 3 / 5',
      batch: 'DRF Batch 12',
      details: {
        before: 'Security 2 / 5',
        after: 'Security 3 / 5',
        triggeredBy: 'Dispute from Ravi Kumar',
        commit: '8f3a2c1',
        entryId: 'aud_01J9X4',
        reason: 'Fix landed before the deadline. Secret key is still hardcoded, so not higher than 3.'
      }
    },
    {
      id: 'aud-2',
      whenDate: 'Today',
      whenTime: '10:15 am',
      whoName: 'Dr. Meera Iyer',
      whoRole: 'Faculty',
      actionType: 'report-published',
      actionLabel: 'Report published',
      target: 'Farhan S., Ticket API with DRF',
      change: '3 reports published together',
      batch: 'DRF Batch 12',
      details: {
        before: 'Unpublished draft',
        after: 'Published live',
        triggeredBy: 'Faculty review & publish',
        commit: '9a2f7c4',
        entryId: 'aud_01J9V2',
        reason: 'All criteria agreed between AI and TA. Published Farhan S. (85%), Sameer J. (58%), and Divya P. (40%).'
      }
    },
    {
      id: 'aud-3',
      whenDate: 'Today',
      whenTime: '9:58 am',
      whoName: 'Priya S.',
      whoRole: 'TA',
      actionType: 'score-overridden',
      actionLabel: 'Score overridden',
      target: 'Anita R., Ticket API with DRF',
      change: 'Testing 1 / 5 to 3 / 5',
      batch: 'DRF Batch 12',
      details: {
        before: 'Testing 1 / 5',
        after: 'Testing 3 / 5',
        triggeredBy: 'TA review',
        commit: '3c8a1b2',
        entryId: 'aud_01J9U1',
        reason: 'Trainee added comprehensive unit tests for views and model validations in test_views.py that were missed by automatic regex evaluator.'
      }
    },
    {
      id: 'aud-4',
      whenDate: 'Yesterday',
      whenTime: '6:20 pm',
      whoName: 'System',
      whoRole: 'Assessor',
      actionType: 'assessment-run',
      actionLabel: 'Assessment run',
      target: 'Sameer J., Pagination and filters',
      change: 'Model qwen2.5 27B, rubric v2',
      batch: 'DRF Batch 12',
      details: {
        before: 'Code submitted',
        after: 'Assessment generated',
        triggeredBy: 'Webhook commit push',
        commit: '5e7b2d1',
        entryId: 'aud_01J8T9',
        reason: 'Automated evaluation run against DRF API design rubric v2.'
      }
    },
    {
      id: 'aud-5',
      whenDate: 'Yesterday',
      whenTime: '4:05 pm',
      whoName: 'Dr. Meera Iyer',
      whoRole: 'Faculty',
      actionType: 'rubric-published',
      actionLabel: 'Rubric published',
      target: 'DRF API design',
      change: 'v2 to v3, 4 criteria',
      batch: 'DRF Batch 12',
      details: {
        before: 'v2 live',
        after: 'v3 live',
        triggeredBy: 'Faculty rubric editor',
        commit: 'rubric-v3',
        entryId: 'aud_01J8R5',
        reason: 'Updated criterion 4 to require explicit token expiry settings in Django Rest Framework.'
      }
    },
    {
      id: 'aud-6',
      whenDate: 'Yesterday',
      whenTime: '11:30 am',
      whoName: 'Priya S.',
      whoRole: 'TA',
      actionType: 'access-denied',
      actionLabel: 'Access denied',
      target: 'Node Batch 4, report list',
      change: 'Not assigned to this batch',
      batch: 'Node Batch 4',
      details: {
        before: 'Access requested',
        after: 'Blocked (403 Forbidden)',
        triggeredBy: 'Role permission policy',
        commit: 'N/A',
        entryId: 'aud_01J8M3',
        reason: 'TA Priya S. is authorized for DRF Batch 12 and DRF Batch 13 only. Access to Node Batch 4 was denied.'
      }
    },
    {
      id: 'aud-7',
      whenDate: '21 Oct',
      whenTime: '3:12 pm',
      whoName: 'Dr. Meera Iyer',
      whoRole: 'Faculty',
      actionType: 'users-invited',
      actionLabel: 'Users invited',
      target: 'DRF Batch 13',
      change: '5 sent, 2 IDs not found',
      batch: 'DRF Batch 13',
      details: {
        before: 'Batch setup',
        after: 'Invitations dispatched',
        triggeredBy: 'Batch roster upload',
        commit: 'N/A',
        entryId: 'aud_01J6K8',
        reason: 'Invited 5 new trainees to cohort DRF Batch 13. 2 employee IDs were missing from directory.'
      }
    }
  */

  // Toggle row expansion
  const toggleRow = (id) => {
    setExpandedRows(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  // Filter entries
  const filteredEntries = useMemo(() => {
    return allAuditEntries.filter(entry => {
      // Search query filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesTarget = entry.target.toLowerCase().includes(query);
        const matchesWho = entry.whoName.toLowerCase().includes(query);
        const matchesChange = entry.change.toLowerCase().includes(query);
        const matchesId = String(entry.details?.entryId || entry.id).toLowerCase().includes(query);
        if (!matchesTarget && !matchesWho && !matchesChange && !matchesId) {
          return false;
        }
      }

      // Who filter
      if (whoFilter !== 'Everyone') {
        if (!entry.whoName.toLowerCase().includes(whoFilter.toLowerCase()) &&
            !entry.whoRole.toLowerCase().includes(whoFilter.toLowerCase())) {
          return false;
        }
      }

      // Action filter
      if (actionFilter !== 'All') {
        if (entry.actionLabel.toLowerCase() !== actionFilter.toLowerCase() &&
            entry.actionType.toLowerCase() !== actionFilter.toLowerCase()) {
          return false;
        }
      }

      // Batch filter
      if (batchFilter !== 'All 3') {
        if (entry.batch !== batchFilter) {
          return false;
        }
      }

      return true;
    });
  }, [searchQuery, whoFilter, actionFilter, batchFilter]);

  // Clear filters
  const handleClearFilters = () => {
    setSearchQuery('');
    setWhoFilter('Everyone');
    setActionFilter('All');
    setBatchFilter('All 3');
    setDateFilter('Last 7 days');
  };

  // Export CSV
  const handleExportCSV = () => {
    const headers = ['Entry ID', 'Date', 'Time', 'Who', 'Role', 'Action', 'Target', 'Change', 'Reason'];
    const rows = filteredEntries.map(e => [
      e.details?.entryId || e.id,
      e.whenDate,
      e.whenTime,
      `"${e.whoName}"`,
      e.whoRole,
      `"${e.actionLabel}"`,
      `"${e.target}"`,
      `"${e.change}"`,
      `"${e.details?.reason || ''}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + 
      [headers.join(','), ...rows.map(r => r.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="admin-audit-container">
      {/* Page Header */}
      <div className="admin-audit-header-row">
        <div className="admin-audit-header-left">
          <div className="admin-audit-title-row">
            <h1 className="admin-audit-title">Audit log</h1>
            <span className="admin-audit-readonly-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Read only
            </span>
          </div>
          <p className="admin-audit-subtitle">
            Every score change, publish and access attempt in your batches. Entries can never be edited or deleted.
          </p>
        </div>

        <div>
          <button
            type="button"
            className="admin-btn-export-csv"
            onClick={handleExportCSV}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export CSV
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="admin-audit-filter-bar">
        {/* Search input */}
        <div className="admin-filter-search-box">
          <span className="admin-filter-search-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            type="text"
            className="admin-filter-search-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search name, task or entry ID"
          />
        </div>

        {/* Who Filter */}
        <select
          className="admin-filter-select"
          value={whoFilter}
          onChange={(e) => setWhoFilter(e.target.value)}
        >
          <option value="Everyone">Who: Everyone</option>
          <option value="Dr. Meera Iyer">Who: Dr. Meera Iyer (Faculty)</option>
          <option value="Priya S.">Who: Priya S. (TA)</option>
          <option value="System">Who: System (Assessor)</option>
        </select>

        {/* Action Filter */}
        <select
          className="admin-filter-select"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        >
          <option value="All">Action: All</option>
          <option value="Score changed">Score changed</option>
          <option value="Report published">Report published</option>
          <option value="Score overridden">Score overridden</option>
          <option value="Assessment run">Assessment run</option>
          <option value="Rubric published">Rubric published</option>
          <option value="Access denied">Access denied</option>
          <option value="Users invited">Users invited</option>
        </select>

        {/* Batch Filter */}
        <select
          className="admin-filter-select"
          value={batchFilter}
          onChange={(e) => setBatchFilter(e.target.value)}
        >
          <option value="All 3">Batch: All 3</option>
          <option value="DRF Batch 12">DRF Batch 12</option>
          <option value="DRF Batch 13">DRF Batch 13</option>
          <option value="Node Batch 4">Node Batch 4</option>
        </select>

        {/* Date Filter */}
        <div 
          className="admin-filter-date-badge"
          onClick={() => {
            const next = dateFilter === 'Last 7 days' ? 'Last 30 days' : 'Last 7 days';
            setDateFilter(next);
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span>{dateFilter}</span>
        </div>
      </div>

      {/* Filter Summary */}
      <div className="admin-audit-filter-summary">
        <span>Showing recorded events in your assigned batches.</span>
        <button
          type="button"
          className="admin-audit-clear-link"
          onClick={handleClearFilters}
        >
          Clear filters
        </button>
      </div>

      {/* Main Table Card */}
      <div className="admin-audit-table-card">
        <table className="admin-audit-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Action</th>
              <th>Target</th>
              <th>Change</th>
              <th style={{ width: '40px' }}></th>
            </tr>
          </thead>
          <tbody>
            {filteredEntries.map((row) => {
              const isExpanded = !!expandedRows[row.id];
              return (
                <React.Fragment key={row.id}>
                  {/* Primary Row */}
                  <tr 
                    className={`admin-audit-row ${isExpanded ? 'expanded' : ''}`}
                    onClick={() => toggleRow(row.id)}
                  >
                    <td>
                      <div className="admin-audit-cell-when">
                        <span className="admin-audit-primary-text">{row.whenDate}</span>
                        <span className="admin-audit-secondary-text">{row.whenTime}</span>
                      </div>
                    </td>

                    <td>
                      <div className="admin-audit-cell-who">
                        <span className="admin-audit-primary-text">{row.whoName}</span>
                        <span className="admin-audit-secondary-text">{row.whoRole}</span>
                      </div>
                    </td>

                    <td>
                      <span className={`admin-action-pill ${row.actionType}`}>
                        {row.actionType === 'score-changed' && (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                          </svg>
                        )}
                        {row.actionType === 'report-published' && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        )}
                        {row.actionType === 'access-denied' && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                          </svg>
                        )}
                        {row.actionLabel}
                      </span>
                    </td>

                    <td style={{ fontWeight: 600 }}>{row.target}</td>

                    <td>{row.change}</td>

                    <td>
                      <button
                        type="button"
                        className="admin-btn-expand-row"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleRow(row.id);
                        }}
                        title={isExpanded ? 'Collapse' : 'Expand'}
                      >
                        <svg 
                          width="12" 
                          height="12" 
                          viewBox="0 0 24 24" 
                          fill="none" 
                          stroke="currentColor" 
                          strokeWidth="2.5"
                          style={{
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.15s ease'
                          }}
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </button>
                    </td>
                  </tr>

                  {/* Expanded Detail Drawer Row */}
                  {isExpanded && row.details && (
                    <tr>
                      <td colSpan={6} className="admin-expanded-drawer-td">
                        <div className="admin-expanded-drawer-content">
                          <div className="admin-expanded-grid">
                            {row.details.before && (
                              <div className="admin-expanded-field">
                                <span className="admin-expanded-field-label">Before</span>
                                <span className="admin-expanded-field-value">{row.details.before}</span>
                              </div>
                            )}

                            {row.details.after && (
                              <div className="admin-expanded-field">
                                <span className="admin-expanded-field-label">After</span>
                                <span className="admin-expanded-field-value">{row.details.after}</span>
                              </div>
                            )}

                            <div className="admin-expanded-field">
                              <span className="admin-expanded-field-label">Triggered by</span>
                              <span className="admin-expanded-field-value">{row.details.triggeredBy}</span>
                            </div>

                            <div className="admin-expanded-field">
                              <span className="admin-expanded-field-label">Commit</span>
                              <span className="admin-expanded-field-value" style={{ fontFamily: 'monospace' }}>
                                {row.details.commit}
                              </span>
                            </div>

                            <div className="admin-expanded-field">
                              <span className="admin-expanded-field-label">Entry ID</span>
                              <span className="admin-expanded-field-value" style={{ fontFamily: 'monospace' }}>
                                {row.details.entryId}
                              </span>
                            </div>
                          </div>

                          {row.details.reason && (
                            <div className="admin-expanded-reason-box">
                              <span className="admin-expanded-field-label">Reason given</span>
                              <div className="admin-expanded-reason-text">
                                {row.details.reason}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>

        {/* Footer / Pagination */}
        <div className="admin-audit-footer">
          <span>Showing {filteredEntries.length} recorded entries</span>
          <div className="admin-audit-pagination">
            <button type="button" className="admin-btn-page" disabled>
              &lt; Previous
            </button>
            <button type="button" className="admin-btn-page">
              Next &gt;
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
