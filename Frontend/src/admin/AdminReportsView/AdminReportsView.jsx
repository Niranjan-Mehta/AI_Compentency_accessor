import React, { useEffect, useState } from 'react';
import './AdminReportsView.css';
import { useApp } from '../../context/AppContext.jsx';

export function AdminReportsView({ onNavigateTab }) {
  const { reports, assessments, api, setAppError, setNotice, refreshWorkspace } = useApp();
  const [trainees, setTrainees] = useState([]);


  const [selectedTraineeId, setSelectedTraineeId] = useState('');
  const [toastNotice, setToastNotice] = useState(null);
  const [traineePreviewModal, setTraineePreviewModal] = useState(null);

  // Active selected trainee
  useEffect(() => { setTrainees(Object.values(reports).map((report) => { const snap = report.snapshot || {}; const override = snap.ta_review?.overrides?.[0]; const overriddenCriterion = snap.criteria?.find((criterion) => criterion.criterion_id === override?.criterion_id); return { id: report.id, reportId: report.id, name: report.trainee_name || snap.trainee?.name || 'Trainee', taskName: report.task_title || snap.task?.title || 'Assessment', batchName: report.batch_name || snap.batch?.name || 'Batch', overallScore: `${report.overall_score}%`, level: report.competency_level, submittedDate: report.created_at ? new Date(report.created_at).toLocaleDateString() : '—', commitHash: '—', published: report.status === 'PUBLISHED', statusType: report.status === 'PUBLISHED' ? 'published' : 'approved', statusLabel: report.status, hasDispute: false, hasOverride: Boolean(override), overrideDetails: override ? { fromScore: `${overriddenCriterion?.ai_score || '—'}/${overriddenCriterion?.max_score || '—'}`, toScore: `${overriddenCriterion?.score || '—'}/${overriddenCriterion?.max_score || '—'}`, taName: override.reviewer || 'TA', statement: override.reason || 'Reviewed score override.' } : null, criteria: (snap.criteria || []).map((c) => ({ name: c.name, aiScore: `${c.ai_score}/${c.max_score}`, taScore: `${c.score}/${c.max_score}`, status: c.overridden_by ? 'Overridden' : 'Reviewed', statusType: c.overridden_by ? 'overridden' : 'agreed' })), disputeResolved: false }; })); }, [reports]);
  useEffect(() => { if (!selectedTraineeId && trainees.length) setSelectedTraineeId(trainees[0].id); }, [selectedTraineeId, trainees]);
  const currentTrainee = trainees.find(t => t.id === selectedTraineeId) || trainees[0] || { id: '', name: 'No reports available', taskName: '—', batchName: '—', overallScore: '—', level: '—', submittedDate: '—', commitHash: '—', published: false, statusType: 'draft', statusLabel: 'No report', hasDispute: false, hasOverride: false, criteria: [] };

  // Forms state for current trainee's dispute - text boxes blank by default
  const [disputeDecision, setDisputeDecision] = useState('change');
  const [disputeNewScore, setDisputeNewScore] = useState('');
  const [disputeReason, setDisputeReason] = useState('');

  // Ready to publish count (approved or resolved, and not yet published)
  const readyToPublishCount = trainees.filter(t => !t.published && t.statusType === 'approved').length;
  const unpreparedRuns = assessments.filter((run) => !Object.values(reports).some((report) => report.assessment_run_id === run.id));
  const handlePrepareReport = async (run) => { try { await api.request('/reports/prepare/', {method:'POST',body:JSON.stringify({assessment_run_id:run.id})}); await refreshWorkspace(); setNotice(`Report prepared for ${run.trainee_name || 'trainee'} · ${run.task_title}.`); } catch (error) { setAppError(error.message); } };

  // Handle saving dispute decision
  const handleSaveDecision = () => setAppError('Dispute decisions are not supported by the backend yet; no report score was changed.');

  // Handle confirming override for Anita
  const handleConfirmOverride = () => setNotice('Existing TA score overrides are reflected in the report snapshot.');

  // Handle single trainee publish
  const handlePublishSingle = async (reportId) => { try { await api.request(`/reports/${reportId}/publish/`, {method:'POST'}); await refreshWorkspace(); setToastNotice({type:'success',message:`Report for ${currentTrainee.name} was published.`}); } catch (error) { setAppError(error.message); } };

  // Handle bulk publish
  const handlePublishBulkReady = async () => {
    for (const report of trainees.filter((t) => !t.published && t.statusType === 'approved')) { try { await api.request(`/reports/${report.reportId}/publish/`, {method:'POST'}); } catch (error) { setAppError(error.message); return; } }
    await refreshWorkspace();

    setToastNotice({
      type: 'success',
      message: `Published ${readyToPublishCount} ready reports to trainees successfully!`
    });
    setTimeout(() => setToastNotice(null), 3500);
  };

  return (
    <div className="admin-reports-container">
      {/* Breadcrumb Navigation */}
      <div className="admin-reports-breadcrumb">
        <span 
          className="admin-reports-breadcrumb-link"
          onClick={() => onNavigateTab && onNavigateTab('overview')}
        >
          Reports
        </span>
        <span className="admin-reports-breadcrumb-separator">&gt;</span>
        <span className="admin-reports-breadcrumb-current">{currentTrainee.taskName}</span>
      </div>

      {/* Page Header */}
      <div className="admin-reports-header-row">
        <div className="admin-reports-header-left">
          <h1 className="admin-reports-title">Review and publish</h1>
          <p className="admin-reports-subtitle">
            {currentTrainee.batchName}. {readyToPublishCount} reports ready for publication. Trainees see only published reports.
          </p>
        </div>

        <div>
          <button
            type="button"
            className="admin-btn-publish-batch"
            disabled={readyToPublishCount === 0}
            onClick={handlePublishBulkReady}
          >
            Publish {readyToPublishCount} ready reports
          </button>
        </div>
      </div>

      {unpreparedRuns.length > 0 && <section className="admin-section-box" style={{marginBottom:20}} aria-label="Completed assessments ready for report preparation"><h2 className="admin-section-heading">Prepare reviewed assessments</h2><div className="admin-decision-items-list">{unpreparedRuns.map((run) => <div key={run.id} className="admin-decision-item"><div className="admin-decision-item-left"><div className="admin-decision-content"><span className="admin-decision-title">{run.task_title}</span><span className="admin-decision-subtitle">{run.trainee_name || `Trainee #${run.trainee_id}`} · Completed {new Date(run.updated_at).toLocaleDateString()}</span></div></div><button type="button" className="admin-decision-action-btn dark" onClick={() => handlePrepareReport(run)}>Prepare report</button></div>)}</div></section>}

      {/* Notification Toast */}
      {toastNotice && (
        <div style={{
          backgroundColor: toastNotice.type === 'success' ? '#ecfdf5' : '#eff6ff',
          border: `1.5px solid ${toastNotice.type === 'success' ? '#10b981' : '#3b82f6'}`,
          borderRadius: '8px',
          padding: '12px 18px',
          marginBottom: '20px',
          color: toastNotice.type === 'success' ? '#065f46' : '#1e40af',
          fontSize: '13.5px',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span>{toastNotice.type === 'success' ? '✓ ' : 'ℹ '}{toastNotice.message}</span>
          <button
            type="button"
            onClick={() => setToastNotice(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main 2-Column Grid */}
      <div className="admin-reports-grid">
        {/* Left Column: Trainees List */}
        <aside className="admin-reports-trainee-list">
          {trainees.map((t) => {
            const isSelected = t.id === currentTrainee.id;
            return (
              <div
                key={t.id}
                className={`admin-reports-trainee-item ${isSelected ? 'active' : ''}`}
                onClick={() => setSelectedTraineeId(t.id)}
              >
                <span className="admin-reports-trainee-name">{t.name}</span>
                <span className={`admin-trainee-item-pill ${t.statusType}`}>
                  {t.statusType === 'dispute' && (
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                  )}
                  {t.statusType === 'override' && (
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 14 14" />
                    </svg>
                  )}
                  {t.statusType === 'approved' && (
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                  {t.statusLabel}
                </span>
              </div>
            );
          })}
        </aside>

        {/* Right Column: Detailed Review Area */}
        <div className="admin-reports-detail-col">
          <div className="admin-trainee-detail-card">
            {/* Header: Trainee Info & Link */}
            <div className="admin-detail-header-row">
              <div className="admin-detail-title-group">
                <h2 className="admin-detail-name">{currentTrainee.name}</h2>
                <p className="admin-detail-subtext">
                  Overall {currentTrainee.overallScore}, {currentTrainee.level}. Submitted {currentTrainee.submittedDate} on commit {currentTrainee.commitHash}.
                </p>
              </div>
              <button
                type="button"
                className="admin-preview-trainee-link"
                onClick={() => setTraineePreviewModal(currentTrainee)}
              >
                Preview as trainee
              </button>
            </div>

            {/* Scores Table */}
            <div className="admin-scores-table-container">
              <table className="admin-scores-table">
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th>AI score</th>
                    <th>TA score</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {currentTrainee.criteria.map((crit, idx) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600 }}>{crit.name}</td>
                      <td>{crit.aiScore}</td>
                      <td>{crit.taScore}</td>
                      <td>
                        <span className={`admin-status-badge ${crit.statusType}`}>
                          {crit.statusType === 'agreed' && (
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                          {crit.statusType === 'disputed' && (
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                            </svg>
                          )}
                          {crit.statusType === 'overridden' && (
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <polyline points="23 4 23 10 17 10" />
                              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                            </svg>
                          )}
                          {crit.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Dispute Decision Box (for Ravi Kumar or active disputes) */}
            {currentTrainee.hasDispute && (
              <div className="admin-decision-box">
                <div className="admin-decision-box-header">
                  <div className="admin-decision-header-left">
                    <span className="admin-decision-p-badge">P</span>
                    <span className="admin-decision-title">
                      {currentTrainee.name} disputes {currentTrainee.disputeDetails.criterion}, {currentTrainee.disputeDetails.score}
                    </span>
                  </div>
                  <span className="admin-decision-deadline">
                    Raised {currentTrainee.disputeDetails.raisedDate}, {currentTrainee.disputeDetails.daysLeft}
                  </span>
                </div>

                {/* Trainee quote */}
                <div className="admin-dispute-quote-box">
                  {currentTrainee.disputeDetails.statement}
                </div>

                {/* Radio Options */}
                <div className="admin-decision-options-group">
                  <span className="admin-decision-options-label">Your decision</span>
                  <div className="admin-radio-options-row">
                    <label 
                      className="admin-radio-item"
                      onClick={() => setDisputeDecision('keep')}
                    >
                      <input
                        type="radio"
                        name="decision"
                        checked={disputeDecision === 'keep'}
                        onChange={() => setDisputeDecision('keep')}
                      />
                      <span>Keep 2 / 5</span>
                    </label>

                    <label 
                      className="admin-radio-item"
                      onClick={() => setDisputeDecision('change')}
                    >
                      <input
                        type="radio"
                        name="decision"
                        checked={disputeDecision === 'change'}
                        onChange={() => setDisputeDecision('change')}
                      />
                      <span>Change to</span>
                      <input
                        type="text"
                        className="admin-radio-input-box"
                        value={disputeNewScore}
                        onChange={(e) => setDisputeNewScore(e.target.value)}
                        maxLength={1}
                      />
                      <span>/ 5</span>
                    </label>

                    <label 
                      className="admin-radio-item"
                      onClick={() => setDisputeDecision('rerun')}
                    >
                      <input
                        type="radio"
                        name="decision"
                        checked={disputeDecision === 'rerun'}
                        onChange={() => setDisputeDecision('rerun')}
                      />
                      <span>Rerun on new commit</span>
                    </label>
                  </div>
                </div>

                {/* Reason Field */}
                <div className="admin-decision-reason-group">
                  <label className="admin-decision-reason-label">
                    Reason (the trainee will see this)
                  </label>
                  <input
                    type="text"
                    className="admin-decision-reason-input"
                    value={disputeReason}
                    onChange={(e) => setDisputeReason(e.target.value)}
                  />
                </div>

                {/* Buttons */}
                <div className="admin-decision-buttons-row">
                  <button
                    type="button"
                    className="admin-btn-save-decision"
                    onClick={handleSaveDecision}
                  >
                    Save decision
                  </button>
                  <button
                    type="button"
                    className="admin-btn-ask-ta"
                    onClick={() => setNotice('Messaging is not configured; no message was sent.')}
                  >
                    Ask TA first
                  </button>
                </div>
              </div>
            )}

            {/* TA Override Box (for Anita R.) */}
            {currentTrainee.hasOverride && (
              <div className="admin-decision-box">
                <div className="admin-decision-box-header">
                  <div className="admin-decision-header-left">
                    <span className="admin-decision-p-badge" style={{ backgroundColor: '#fff7ed', color: '#c2410c' }}>O</span>
                    <span className="admin-decision-title">
                      TA raised a Testing score: {currentTrainee.overrideDetails.fromScore} changed to {currentTrainee.overrideDetails.toScore} by {currentTrainee.overrideDetails.taName}
                    </span>
                  </div>
                </div>

                <div className="admin-dispute-quote-box">
                  {currentTrainee.overrideDetails.statement}
                </div>

                <div className="admin-decision-buttons-row">
                  <button
                    type="button"
                    className="admin-btn-save-decision"
                    onClick={handleConfirmOverride}
                  >
                    Confirm override
                  </button>
                  <button
                    type="button"
                    className="admin-btn-ask-ta"
                    onClick={() => setNotice('Score overrides cannot be reverted from this page. No score was changed.')}
                  >
                    Revert to AI score
                  </button>
                </div>
              </div>
            )}

            {/* Footer Publish Single Trainee */}
            <div className="admin-trainee-publish-footer">
              <button
                type="button"
                className="admin-btn-publish-single"
                disabled={
                  currentTrainee.published || 
                  (currentTrainee.hasDispute && !currentTrainee.disputeResolved)
                }
                onClick={() => handlePublishSingle(currentTrainee.id)}
              >
                {currentTrainee.published ? 'Report published' : 'Publish report'}
              </button>

              {currentTrainee.hasDispute && !currentTrainee.disputeResolved && (
                <span className="admin-publish-requirement-hint">
                  Save a decision on the dispute to publish this report.
                </span>
              )}

              {currentTrainee.published && (
                <span className="admin-publish-requirement-hint" style={{ color: '#047857', fontWeight: 600 }}>
                  ✓ This report is live and visible on the trainee dashboard.
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Trainee Preview Modal */}
      {traineePreviewModal && (
        <div className="modal-overlay" style={{ zIndex: 1000 }}>
          <div className="modal-dialog" style={{ maxWidth: '580px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 className="modal-dialog-title" style={{ margin: 0 }}>
                  Student View Preview: {traineePreviewModal.name}
                </h3>
                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>
                  Task: {traineePreviewModal.taskName} • Level: {traineePreviewModal.level}
                </span>
              </div>
              <button
                type="button"
                className="btn-remove-file"
                onClick={() => setTraineePreviewModal(null)}
              >
                ✕
              </button>
            </div>

            <p className="modal-dialog-desc">
              This preview shows the finalized scorecard as it will be seen by the student trainee upon publishing:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
              {traineePreviewModal.criteria.map((c, i) => (
                <div 
                  key={i} 
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    padding: '10px 14px', 
                    borderRadius: '6px', 
                    border: '1.5px solid var(--border-color, #60a5fa)',
                    backgroundColor: '#ffffff'
                  }}
                >
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>{c.name}</span>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: '#2563eb' }}>{c.taScore}</span>
                </div>
              ))}
            </div>

            <div className="modal-buttons-row">
              <button
                type="button"
                className="btn-primary-submit"
                onClick={() => setTraineePreviewModal(null)}
                style={{ width: '100%' }}
              >
                Close preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
