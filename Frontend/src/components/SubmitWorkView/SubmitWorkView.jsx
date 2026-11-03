import React, { useState, useEffect } from 'react';
import './SubmitWorkView.css';
import { useApp } from '../../context/AppContext.jsx';

export const SubmitWorkView = ({ onNavigate, onSubmitSuccess }) => {
  const { tasks, activeTaskId, submitWork, currentUser } = useApp();

  const currentTask = tasks.find((t) => t.id === activeTaskId) || tasks[0];

  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState(currentTask?.branch || 'main');
  const [file, setFile] = useState(null);
  const [hasPdf, setHasPdf] = useState(false);
  const [pdfName, setPdfName] = useState('');
  const [pdfMeta, setPdfMeta] = useState('');
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (currentTask) {
      setBranch(currentTask.branch || 'main');
      setHasPdf(false);
      setFile(null);
      setPdfName('');
    }
  }, [currentTask]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isConfirmed) {
      alert('Please check the confirmation box: "I confirm this is my own work".');
      return;
    }
    if (!repoUrl.trim()) { alert('Enter your Git repository URL.'); return; }
    if (currentTask.require_pdf && !file) { alert('Choose the required project PDF.'); return; }
    setIsSubmitting(true);
    try {
      await submitWork(currentTask.id, { repoUrl, branch, file });
      onSubmitSuccess?.();
      onNavigate('dashboard');
    } catch (error) { alert(error.message || 'Submission failed.'); }
    finally { setIsSubmitting(false); }
  };

  const handleFileUpload = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setPdfName(file.name);
      setFile(file);
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      setPdfMeta(`${sizeMb} MB, document readable`);
      setHasPdf(true);
    }
  };

  if (!currentTask) return <div className="main-wrapper"><nav className="breadcrumb-nav"><span className="breadcrumb-link" onClick={() => onNavigate('dashboard')}>Dashboard</span><span className="breadcrumb-separator">&gt;</span><span className="breadcrumb-current">Submit your work</span></nav><h1 className="page-title">Submit your work</h1><p className="page-subtitle">There are no active tasks available for submission.</p><button className="btn-secondary-cancel" onClick={() => onNavigate('dashboard')}>Back to dashboard</button></div>;

  return (
    <div className="main-wrapper">
      {/* Breadcrumb Navigation */}
      <nav className="breadcrumb-nav">
        <span 
          className="breadcrumb-link" 
          onClick={() => onNavigate('dashboard')}
        >
          Dashboard
        </span>
        <span className="breadcrumb-separator">&gt;</span>
        <span className="breadcrumb-current">{currentTask?.name || 'Submit your work'}</span>
      </nav>

      {/* Page Title with Amber Due Badge */}
      <div className="page-heading-group">
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          <h1 className="page-title" style={{ margin: 0 }}>Submit your work</h1>
          <span className="badge-header-warning">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            {currentTask?.dueText || 'Due tomorrow, 11:59 pm'}
          </span>
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="two-column-layout">
        {/* Left Form Column */}
        <form onSubmit={handleSubmit} className="form-column">
          {/* Gitea repository URL */}
          <div className="form-group">
            <label className="form-label" htmlFor="gitea-repo-input">
              Git repository URL
            </label>
            <input 
              id="gitea-repo-input"
              type="text" 
              className="text-input-field" 
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://gitea.internal/your-name/repo"
            />
            <div className="input-status-note">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>{repoUrl ? `Repository URL entered. Target branch: ${branch}` : `Target branch: ${branch}`}</span>
            </div>
          </div>

          {/* Branch dropdown */}
          <div className="form-group">
            <label className="form-label" htmlFor="branch-select">
              Branch
            </label>
            <select 
              id="branch-select"
              className="select-dropdown"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
            >
              <option value="main">main</option>
              <option value="feature/ticket-views">feature/ticket-views</option>
              <option value="feature/jwt-auth">feature/jwt-auth</option>
              <option value="dev">dev</option>
            </select>
          </div>

          {/* Learning document (PDF) */}
          <div className="form-group">
            <label className="form-label">
              Learning document (PDF)
            </label>

            {hasPdf && (
              <div className="uploaded-file-card">
                <div className="uploaded-file-left">
                  <div className="file-icon-box">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  </div>
                  <div>
                    <div className="uploaded-file-name">{pdfName}</div>
                    <div className="uploaded-file-meta">{pdfMeta}</div>
                  </div>
                </div>

                <div className="uploaded-file-right">
                  <div className="icon-checked-green" title="Document verified">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                  <button 
                    type="button" 
                    className="btn-remove-file" 
                    title="Remove PDF"
                    onClick={() => setHasPdf(false)}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </div>
              </div>
            )}

            {/* Drag & Drop Box */}
            <label className="dropzone-box" htmlFor="pdf-file-upload">
              <input 
                id="pdf-file-upload"
                type="file" 
                accept=".pdf" 
                style={{ display: 'none' }} 
                onChange={handleFileUpload}
              />
              <div className="dropzone-upload-circle">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
              </div>
              <div className="dropzone-primary-text">
                Drag your PDF here or <span className="dropzone-link">browse files</span>
              </div>
              <div className="dropzone-subtext">
                {currentTask?.require_pdf ? 'PDF required. Up to 10 MB. Scanned pages cannot be read.' : 'PDF optional for this task. Up to 10 MB.'}
              </div>
            </label>
          </div>

          {/* Confirm own work Checkbox */}
          <div 
            className="confirm-checkbox-row"
            onClick={() => setIsConfirmed(!isConfirmed)}
          >
            <div className={`checkbox-custom ${isConfirmed ? 'checked' : ''}`}>
              {isConfirmed && (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              )}
            </div>
            <span>I confirm this is my own work</span>
          </div>

          {/* Action buttons */}
          <div className="form-buttons-row">
            <button 
              type="submit" 
              className="btn-primary-submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Submitting...' : 'Submit for assessment'}
            </button>
            <button 
              type="button" 
              className="btn-secondary-cancel"
              onClick={() => onNavigate('dashboard')}
            >
              Cancel
            </button>
          </div>
        </form>

        {/* Right Info Column */}
        <div className="side-column">
          {/* Card 1: Before you submit */}
          <div className="side-card">
            <h3 className="side-card-title">Before you submit</h3>
            <div className="checklist-group">
              <div className="checklist-item">
                <span className="checklist-check-icon">✓</span>
                <span>Push your latest code to Gitea</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check-icon">✓</span>
                <span>Give the assessor account read access</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check-icon">✓</span>
                <span>Your PDF explains what you built and why</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check-icon">✓</span>
                <span>{currentTask.allow_resubmission ? 'Resubmission is enabled until the due date' : 'Resubmission is disabled for this task'}</span>
              </div>
            </div>
          </div>

          {/* Card 2: What happens next */}
          <div className="side-card">
            <h3 className="side-card-title">What happens next</h3>
            <div className="steps-list">
              <div className="step-item">
                <div className="step-number-circle">1</div>
                <div>
                  <div className="step-text-title">We read your code</div>
                  <div className="step-text-desc">Takes about 2 minutes</div>
                </div>
              </div>

              <div className="step-item">
                <div className="step-number-circle">2</div>
                <div>
                  <div className="step-text-title">AI scores each rubric point</div>
                  <div className="step-text-desc">Every score links to a file and line</div>
                </div>
              </div>

              <div className="step-item">
                <div className="step-number-circle">3</div>
                <div>
                  <div className="step-text-title">Questions are ready</div>
                  <div className="step-text-desc">You get a notification on the dashboard</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
