import React, { useState } from 'react';
import './ReportDetailView.css';
import { useApp } from '../../context/AppContext.jsx';

export const ReportDetailView = ({ onNavigate }) => {
  const {
    reports,
    activeReportId,
    setActiveReportId,
    getReport,
    setNotice
  } = useApp();

  const report = getReport(activeReportId);

  // In Image 4, Security is expanded by default (or the last criterion)
  const [expandedIds, setExpandedIds] = useState(['security']);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewNote, setReviewNote] = useState('');

  const toggleExpand = (id) => {
    if (expandedIds.includes(id)) {
      setExpandedIds(expandedIds.filter((item) => item !== id));
    } else {
      setExpandedIds([...expandedIds, id]);
    }
  };

  const handleRequestReview = () => {
    if (!reviewNote.trim()) {
      alert('Please specify which criterion and reason for review.');
      return;
    }
    setNotice('Review requests are not available in the backend yet. No request was sent.');
    setShowReviewModal(false);
    setReviewNote('');
  };

  const availableReports = Object.values(reports);

  if (!report) return <div className="main-wrapper"><h1 className="page-title">My reports</h1><p className="page-subtitle">Published assessment reports will appear here.</p><button className="btn-secondary-cancel" onClick={() => onNavigate('dashboard')}>Back to dashboard</button></div>;

  return (
    <div className="main-wrapper">
      {/* Breadcrumb Navigation: My reports > Report Name */}
      <nav className="breadcrumb-nav" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span 
            className="breadcrumb-link" 
            onClick={() => onNavigate('dashboard')}
          >
            My reports
          </span>
          <span className="breadcrumb-separator">&gt;</span>
          <span className="breadcrumb-current">{report.taskName}</span>
        </div>

        {/* Dynamic Report Switcher dropdown if multiple reports exist */}
        {availableReports.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>Switch report:</span>
            <select
              value={report.id}
              onChange={(e) => setActiveReportId(e.target.value)}
              className="select-dropdown"
              style={{ width: 'auto', padding: '4px 10px', fontSize: '13px' }}
            >
              {availableReports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.taskName} ({r.overallScore}%)
                </option>
              ))}
            </select>
          </div>
        )}
      </nav>

      {/* Header with Title and Green Published Badge */}
      <div className="page-heading-group" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          <h1 className="page-title" style={{ margin: 0 }}>{report.taskName}</h1>
          <span className="status-pill published">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            Published
          </span>
        </div>
        <p className="page-subtitle" style={{ marginTop: '6px' }}>
          Reviewed by {report.reviewedBy} on {report.reviewDate}. Rubric: {report.rubric}.
        </p>
      </div>

      {/* Two-Column Master Layout matching Image 4 */}
      <div className="report-grid-layout">
        
        {/* LEFT COLUMN: Top 2 score cards + Score by criterion list */}
        <div>
          {/* Pair of Metric Cards side-by-side */}
          <div className="report-stat-cards">
            {/* Card 1: Overall score */}
            <div className="stat-card" style={{ padding: '20px 24px' }}>
              <div className="stat-card-title">Overall score</div>
              <div className="stat-card-value">{report.overallScore}%</div>
              <div className="stat-card-desc">Weighted across {report.criteria.length} criteria</div>
            </div>

            {/* Card 2: Level for this skill */}
            <div className="stat-card" style={{ padding: '20px 24px' }}>
              <div className="stat-card-title">Level for this skill</div>
              <div className="stat-card-value">{report.level}</div>
              <div className="stat-card-desc">{report.levelDesc}</div>
            </div>
          </div>

          {/* Score by Criterion Section */}
          <div style={{ marginTop: '12px' }}>
            <h2 className="criteria-section-title">
              Score by criterion
            </h2>

            <div className="criteria-list">
              {report.criteria.map((criterion) => {
                const isExpanded = expandedIds.includes(criterion.id);
                const fillPercentage = (criterion.score / criterion.maxScore) * 100;

                return (
                  <div key={criterion.id} className="criterion-row">
                    <div className="criterion-header">
                      <div className="criterion-name">
                        {criterion.name}
                      </div>
                      
                      <div className="criterion-bar-track">
                        <div 
                          className="criterion-bar-fill" 
                          style={{ width: `${fillPercentage}%` }}
                        ></div>
                      </div>

                      <div className="criterion-score-text">
                        {criterion.score} / {criterion.maxScore}
                      </div>

                      <button 
                        type="button" 
                        className="btn-accordion-toggle"
                        onClick={() => toggleExpand(criterion.id)}
                        title={isExpanded ? 'Collapse evidence' : 'Expand evidence'}
                      >
                        {isExpanded ? (
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="18 15 12 9 6 15"></polyline>
                          </svg>
                        ) : (
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                          </svg>
                        )}
                      </button>
                    </div>

                    {/* Evidence Expansion Box */}
                    {isExpanded && criterion.evidence && (
                      <div className="evidence-box">
                        <div className="evidence-title">
                          Evidence
                        </div>
                        
                        {criterion.evidence.files.map((item, idx) => (
                          <div key={idx} className="evidence-item">
                            <span className="evidence-file">
                              {item.file}
                            </span>
                            <span>{item.note}</span>
                          </div>
                        ))}

                        {criterion.evidence.learnNext && (
                          <div className="evidence-learn-next">
                            <span style={{ fontWeight: 600 }}>Learn next:</span> {criterion.evidence.learnNext}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Feedback from your TA & Disagree with a score? */}
        <div className="report-side-cards">
          {/* Card 1: Feedback from your TA */}
          <div className="stat-card" style={{ padding: '20px 24px' }}>
            <h3 className="report-card-heading">
              Feedback from your TA
            </h3>
            <p className="report-card-text">
              {report.taFeedback}
            </p>
          </div>

          {/* Card 2: Disagree with a score? */}
          <div className="stat-card" style={{ padding: '20px 24px' }}>
            <h3 className="report-card-heading">
              Disagree with a score?
            </h3>
            <p className="report-card-text" style={{ marginBottom: '16px' }}>
              You can ask your TA to look again within 7 days of publishing. Say which criterion and why.
            </p>
            <button 
              type="button" 
              className="btn-secondary-cancel"
              onClick={() => setShowReviewModal(true)}
              style={{ width: '100%', textAlign: 'center' }}
            >
              Request a review
            </button>

            {/* Dynamic Pending Reviews List */}
            {report.reviewRequests && report.reviewRequests.length > 0 && (
              <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: '#0369a1' }}>Submitted Review Requests:</span>
                {report.reviewRequests.map((req) => (
                  <div key={req.id} style={{ fontSize: '11px', background: '#f0f9ff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px', marginTop: '6px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: '#0f172a' }}>
                      <span>Status: {req.status}</span>
                      <span>{req.date}</span>
                    </div>
                    <p style={{ margin: '4px 0 0 0', color: '#475569' }}>"{req.note}"</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Request Review Modal */}
      {showReviewModal && (
        <div className="modal-overlay">
          <div className="modal-dialog">
            <h3 className="modal-dialog-title">
              Request a Score Review
            </h3>
            <p className="modal-dialog-desc">
              You can ask your TA to look again within 7 days of publishing (until 1 Oct). Say which criterion and why:
            </p>

            <textarea 
              value={reviewNote}
              onChange={(e) => setReviewNote(e.target.value)}
              placeholder="e.g. Regarding Security (settings.py:23): I moved SECRET_KEY to decouple in branch fix/security-config..."
              rows={4}
              className="modal-textarea"
            />

            <div className="modal-buttons-row">
              <button 
                type="button" 
                className="btn-secondary-cancel"
                onClick={() => setShowReviewModal(false)}
              >
                Cancel
              </button>
              <button 
                type="button" 
                className="btn-primary-submit"
                onClick={handleRequestReview}
              >
                Submit Request
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
