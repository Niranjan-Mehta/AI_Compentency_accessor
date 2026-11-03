import React, { useMemo, useState } from 'react';
import './AdminOverviewView.css';
import { useApp } from '../../context/AppContext.jsx';

export const AdminOverviewView = ({ onNavigateTab, onActionClick }) => {
  const { currentUser, batches, tasks, reports, api, setAppError, setNotice, refreshWorkspace } = useApp();
  const adminUser = { name: currentUser?.first_name || currentUser?.fullName?.split(' ')[0] || 'there' };
  const adminBatches = batches.map((b) => ({ ...b, traineeCount: b.trainee_count || 0, taName: b.tas?.map((ta) => ta.first_name || ta.username).join(', ') || 'unassigned', completedTasks: tasks.filter((t) => t.status === 'COMPLETED' && t.batches?.some((x) => x.id === b.id)).length, totalTasks: tasks.filter((t) => t.batches?.some((x) => x.id === b.id)).length || 0 }));
  const reportRows = Object.values(reports);
  const decisions = useMemo(() => reportRows.filter((r) => r.status === 'DRAFT').map((r) => ({ id: r.id, type: 'ready-to-publish', typeLabel: 'Ready to publish', title: r.task?.title || r.task_title || 'Assessment report', subtitle: `${r.trainee_name || 'Trainee'} · ${r.batch?.name || r.batch_name || 'Batch'}`, actionLabel: 'Review and publish', actionType: 'review-publish' })), [reports]);
  const averageScore = reportRows.length ? Math.round(reportRows.reduce((sum, r) => sum + Number(r.overall_score || 0), 0) / reportRows.length) : 0;
  const stats = { activeTrainees: batches.reduce((sum, b) => sum + (b.trainee_count || 0), 0), activeTraineesDesc: `Across ${batches.length} batches`, reportsToPublish: decisions.length, reportsToPublishDesc: 'Reviewed reports waiting for publication', openDisputes: 0, openDisputesDesc: 'Dispute requests are not enabled', averageScore, averageScoreDesc: 'Across available assessment reports' };
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('Trainee');
  const [inviteBatch, setInviteBatch] = useState('DRF Batch 12');

  const [activeDisputeModal, setActiveDisputeModal] = useState(null);
  const [disputeNotes, setDisputeNotes] = useState('');

  // Handle decisions
  const handleDecisionAction = (item) => {
    if (item.actionType === 'review-publish') {
      if (onActionClick) {
        onActionClick('review-publish', item);
      } else if (onNavigateTab) {
        onNavigateTab('reports');
      }
    } else if (item.actionType === 'open-dispute') {
      setActiveDisputeModal(item);
    } else if (item.actionType === 'confirm-override') {
      // Confirmed TA override
      setNotice('Score overrides are managed through assessment review.');
    }
  };

  const handleResolveDispute = (decision) => {
    setNotice('Dispute management is not available in the backend yet. No score was changed.');
    setActiveDisputeModal(null);
    setDisputeNotes('');
  };

  const handleSendInvite = (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) {
      alert('Please enter an email address.');
      return;
    }
    const role = inviteRole === 'Trainee' ? 'TRAINEE' : inviteRole.startsWith('Teaching') ? 'TA' : 'FACULTY';
    const batch = batches.find((item) => item.name === inviteBatch);
    api.request('/auth/invite/', { method: 'POST', body: JSON.stringify({ email: inviteEmail, role, batch_id: batch?.id || null, send_email: true }) }).then(async () => { setNotice(`Invitation sent to ${inviteEmail}.`); await refreshWorkspace(); setShowInviteModal(false); setInviteEmail(''); }).catch((error) => setAppError(error.message));
  };

  return (
    <div className="admin-overview-container">
      {/* Page Title & Action Buttons Header */}
      <div className="admin-overview-header-row">
        <div className="admin-overview-title-group">
          <h1 className="admin-overview-title">Good morning, {adminUser.name}</h1>
          <p className="admin-overview-subtitle">
            {batches.length} batches running. {decisions.length} items need your decision.
          </p>
        </div>

        <div className="admin-overview-actions">
          <button 
            type="button" 
            className="admin-btn-secondary"
            onClick={() => setShowInviteModal(true)}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="4" width="20" height="16" rx="2"></rect>
              <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
            </svg>
            Invite people
          </button>

          <button 
            type="button" 
            className="admin-btn-primary"
            onClick={() => onNavigateTab ? onNavigateTab('create-task') : alert('Navigating to Create Task')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            Create task
          </button>
        </div>
      </div>

      {/* 4 Stat Cards Grid */}
      <div className="admin-stat-cards-grid">
        {/* Card 1: Active trainees */}
        <div className="admin-stat-card">
          <div className="admin-stat-card-title">Active trainees</div>
          <div className="admin-stat-card-value">{stats.activeTrainees}</div>
          <div className="admin-stat-card-desc">{stats.activeTraineesDesc}</div>
        </div>

        {/* Card 2: Reports to publish */}
        <div className="admin-stat-card">
          <div className="admin-stat-card-title">Reports to publish</div>
          <div className="admin-stat-card-value">{stats.reportsToPublish}</div>
          <div className="admin-stat-card-desc">{stats.reportsToPublishDesc}</div>
        </div>

        {/* Card 3: Open disputes */}
        <div className="admin-stat-card">
          <div className="admin-stat-card-title">Open disputes</div>
          <div className="admin-stat-card-value">{stats.openDisputes}</div>
          <div className="admin-stat-card-desc">{stats.openDisputesDesc}</div>
        </div>

        {/* Card 4: Average score */}
        <div className="admin-stat-card">
          <div className="admin-stat-card-title">Average score</div>
          <div className="admin-stat-card-value">{stats.averageScore}%</div>
          <div className="admin-stat-card-desc">{stats.averageScoreDesc}</div>
        </div>
      </div>

      {/* Two Column Layout: Needs your decision & Your batches */}
      <div className="admin-overview-columns-grid">
        
        {/* LEFT COLUMN: Needs your decision */}
        <div className="admin-section-box">
          <h2 className="admin-section-heading">Needs your decision</h2>

          <div className="admin-decision-items-list">
            {decisions.map((item) => (
              <div key={item.id} className="admin-decision-item">
                <div className="admin-decision-item-left">
                  {/* Status Pills */}
                  {item.type === 'ready-to-publish' && (
                    <span className="admin-decision-pill ready-to-publish">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                      </svg>
                      {item.typeLabel}
                    </span>
                  )}

                  {item.type === 'dispute' && (
                    <span className="admin-decision-pill dispute">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                      </svg>
                      {item.typeLabel}
                    </span>
                  )}

                  {item.type === 'override' && (
                    <span className="admin-decision-pill override">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                      </svg>
                      {item.typeLabel}
                    </span>
                  )}

                  {/* Content details */}
                  <div className="admin-decision-content">
                    <span className="admin-decision-title">{item.title}</span>
                    <span className="admin-decision-subtitle">{item.subtitle}</span>
                  </div>
                </div>

                {/* Action button */}
                <button
                  type="button"
                  className={`admin-decision-action-btn ${item.actionType === 'review-publish' ? 'dark' : 'outline'}`}
                  onClick={() => handleDecisionAction(item)}
                >
                  {item.actionLabel}
                </button>
              </div>
            ))}

            {decisions.length === 0 && (
              <div style={{ padding: '24px 0', textAlign: 'center', color: '#64748b', fontSize: '13.5px' }}>
                All pending decisions have been addressed! Great job.
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Your batches */}
        <div className="admin-section-box">
          <h2 className="admin-section-heading">Your batches</h2>

          <div className="admin-batches-list">
            {adminBatches.map((batch) => {
              const fillPct = (batch.completedTasks / batch.totalTasks) * 100;

              return (
                <div 
                  key={batch.id} 
                  className="admin-batch-card-item"
                  onClick={() => onNavigateTab ? onNavigateTab('batches') : null}
                  title={`View ${batch.name} details`}
                >
                  <div className="admin-batch-header-line">
                    <span className="admin-batch-name">{batch.name}</span>
                    <span className="admin-batch-chevron">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                      </svg>
                    </span>
                  </div>

                  <span className="admin-batch-subtitle">
                    {batch.traineeCount} trainees, TA {batch.taName}
                  </span>

                  <div className="admin-batch-progress-row">
                    <div className="admin-batch-progress-track">
                      <div 
                        className="admin-batch-progress-fill" 
                        style={{ width: `${fillPct}%` }}
                      ></div>
                    </div>
                    <span className="admin-batch-progress-label">
                      {batch.completedTasks} of {batch.totalTasks} tasks
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* Invite People Modal */}
      {showInviteModal && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-dialog">
            <div className="admin-modal-header">
              <h3 className="admin-modal-title">Invite to Batch</h3>
              <button 
                type="button" 
                className="admin-modal-close-btn"
                onClick={() => setShowInviteModal(false)}
              >
                ✕
              </button>
            </div>

            <p className="admin-modal-desc">
              Send an email invitation link to join the competency assessor platform.
            </p>

            <form onSubmit={handleSendInvite}>
              <div className="admin-modal-form-group">
                <label className="admin-modal-label">Email address</label>
                <input 
                  type="email"
                  className="admin-modal-input"
                  placeholder="trainee@institution.edu"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  required
                />
              </div>

              <div className="admin-modal-form-group">
                <label className="admin-modal-label">Role</label>
                <select 
                  className="admin-modal-select"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                >
                  <option value="Trainee">Trainee</option>
                  <option value="Teaching Assistant (TA)">Teaching Assistant (TA)</option>
                </select>
              </div>

              <div className="admin-modal-form-group">
                <label className="admin-modal-label">Assign to Batch</label>
                <select 
                  className="admin-modal-select"
                  value={inviteBatch}
                  onChange={(e) => setInviteBatch(e.target.value)}
                >
                  {adminBatches.map((b) => (
                    <option key={b.id} value={b.name}>{b.name}</option>
                  ))}
                </select>
              </div>

              <div className="admin-modal-buttons-row">
                <button 
                  type="button" 
                  className="admin-btn-secondary"
                  onClick={() => setShowInviteModal(false)}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="admin-btn-primary"
                >
                  Send invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Dispute Review Modal */}
      {activeDisputeModal && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-dialog">
            <div className="admin-modal-header">
              <h3 className="admin-modal-title">Review Score Dispute</h3>
              <button 
                type="button" 
                className="admin-modal-close-btn"
                onClick={() => setActiveDisputeModal(null)}
              >
                ✕
              </button>
            </div>

            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color, #60a5fa)', borderRadius: '6px', padding: '12px 14px', marginBottom: '14px' }}>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                {activeDisputeModal.traineeName} • {activeDisputeModal.taskName}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                Criterion: <strong>{activeDisputeModal.criterion}</strong> (Current score: {activeDisputeModal.scoreText})
              </div>
              <p style={{ fontSize: '12px', color: '#334155', margin: '8px 0 0 0', fontStyle: 'italic' }}>
                "{activeDisputeModal.traineeName} states: I moved SECRET_KEY into an environment file in commit 8f3a2c1 before deadline."
              </p>
            </div>

            <div className="admin-modal-form-group">
              <label className="admin-modal-label">Faculty decision note (visible in audit log)</label>
              <textarea 
                className="admin-modal-textarea"
                rows={3}
                placeholder="e.g. Verified commit timestamp. Secret key was properly decoupled."
                value={disputeNotes}
                onChange={(e) => setDisputeNotes(e.target.value)}
              />
            </div>

            <div className="admin-modal-buttons-row">
              <button 
                type="button" 
                className="admin-btn-secondary"
                onClick={() => handleResolveDispute('reject')}
              >
                Keep {activeDisputeModal.scoreText}
              </button>
              <button 
                type="button" 
                className="admin-btn-primary"
                onClick={() => handleResolveDispute('accept')}
              >
                Accept Dispute (+1 point)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
