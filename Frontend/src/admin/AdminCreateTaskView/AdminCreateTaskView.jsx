import React, { useState } from 'react';
import './AdminCreateTaskView.css';
import { useApp } from '../../context/AppContext.jsx';

export function AdminCreateTaskView({ onNavigateTab }) {
  const { batches, rubrics, api, refreshWorkspace, setAppError } = useApp();
  // All text boxes start blank as requested
  const [taskTitle, setTaskTitle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [skill, setSkill] = useState('Auth and security');
  const [rubric, setRubric] = useState('');
  const [selectedBatches, setSelectedBatches] = useState([]);
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [questionsCount, setQuestionsCount] = useState('6');
  const [requirePdf, setRequirePdf] = useState(true);
  const [allowResubmission, setAllowResubmission] = useState(true);

  // Success feedback banner
  const [actionNotice, setActionNotice] = useState(null);

  // Batch choices come from the current faculty account's backend scope.
  const batchOptions = batches.map((batch) => ({ id: batch.id, name: batch.name, traineeCount: batch.trainee_count || 0, subtext: `${batch.trainee_count || 0} trainees · ${batch.ta_count || 0} TAs`, compatible: true }));


  // Toggle batch selection
  const handleToggleBatch = (batchId) => {
    if (selectedBatches.includes(batchId)) {
      setSelectedBatches(selectedBatches.filter(id => id !== batchId));
    } else {
      setSelectedBatches([...selectedBatches, batchId]);
    }
  };

  // Dynamic calculation of total assigned trainees
  const totalTrainees = batchOptions
    .filter(b => selectedBatches.includes(b.id))
    .reduce((sum, b) => sum + b.traineeCount, 0);

  // Form submit handler
  const handleAssignTask = async (e, activate = true) => {
    e?.preventDefault();
    if (!taskTitle.trim()) {
      alert('Please enter a task title.');
      return;
    }
    if (selectedBatches.length === 0) {
      alert('Please select at least one batch to assign.');
      return;
    }

    try {
      const saved = await api.request('/tasks/', { method: 'POST', body: JSON.stringify({ title: taskTitle, description: instructions, skill, rubric: Number(rubric), batches: selectedBatches.map(Number), due_date: dueDate ? new Date(`${dueDate}T${dueTime || '23:59'}`).toISOString() : null, questions_count: Number(questionsCount), require_pdf: requirePdf, allow_resubmission: allowResubmission }) });
      if (activate) await api.request(`/tasks/${saved.id}/activate/`, { method: 'POST' });
      await refreshWorkspace();
      setActionNotice({ type: 'success', message: activate ? `Task "${taskTitle}" assigned to ${totalTrainees} trainees across ${selectedBatches.length} batches.` : `Draft "${taskTitle}" saved.` });
      if (activate) window.setTimeout(() => onNavigateTab?.('batches'), 1000);
    } catch (error) { setAppError(error.message); }
  };

  // Save as draft handler
  const handleSaveDraft = (e) => {
    e?.preventDefault();
    if (!taskTitle.trim() || !instructions.trim() || !rubric || !selectedBatches.length) { setAppError('Enter a title, instructions, rubric and at least one batch before saving.'); return; }
    handleAssignTask(e, false);
  };

  // Formatting date preview (e.g., "3 Oct 2026" -> "Due 3 Oct, 11:59 pm")
  const formattedDuePreview = () => {
    const dateClean = dueDate.replace(' 2026', '').trim();
    return `Due ${dateClean}, ${dueTime}`;
  };

  return (
    <div className="admin-create-task-container">
      {/* Breadcrumb Navigation */}
      <div className="admin-create-task-breadcrumb">
        <span 
          className="admin-create-task-breadcrumb-link"
          onClick={() => onNavigateTab && onNavigateTab('overview')}
        >
          Overview
        </span>
        <span className="admin-create-task-breadcrumb-separator">&gt;</span>
        <span className="admin-create-task-breadcrumb-current">Create task</span>
      </div>

      {/* Page Header */}
      <h1 className="admin-create-task-title">Create a task</h1>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div style={{
          backgroundColor: actionNotice.type === 'success' ? '#ecfdf5' : '#eff6ff',
          border: `1.5px solid ${actionNotice.type === 'success' ? '#10b981' : '#3b82f6'}`,
          borderRadius: '8px',
          padding: '12px 18px',
          marginBottom: '20px',
          color: actionNotice.type === 'success' ? '#065f46' : '#1e40af',
          fontSize: '13.5px',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span>{actionNotice.type === 'success' ? '✓ ' : 'ℹ '}{actionNotice.message}</span>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main 2-Column Grid */}
      <div className="admin-create-task-grid">
        {/* Left: Form Area */}
        <form className="admin-create-task-form" onSubmit={handleAssignTask}>
          {/* Task Title */}
          <div className="admin-form-group">
            <label className="admin-form-label" htmlFor="task-title-input">
              Task title
            </label>
            <input
              id="task-title-input"
              type="text"
              className="admin-form-input"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              placeholder="e.g. JWT auth for Ticket API"
            />
          </div>

          {/* Instructions for Trainees */}
          <div className="admin-form-group">
            <label className="admin-form-label" htmlFor="task-instructions-input">
              Instructions for trainees
            </label>
            <textarea
              id="task-instructions-input"
              className="admin-form-textarea"
              rows={4}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Add clear requirements and constraints for the trainees..."
            />
            <div className="admin-form-subtext">
              Shown on the submit page. Keep it to what they must build.
            </div>
          </div>

          {/* 2-Column Row: Skill & Rubric */}
          <div className="admin-form-row-2col">
            <div className="admin-form-group">
              <label className="admin-form-label" htmlFor="task-skill-select">
                Skill
              </label>
              <select
                id="task-skill-select"
                className="admin-form-select"
                value={skill}
                onChange={(e) => setSkill(e.target.value)}
              >
                <option value="Auth and security">Auth and security</option>
                <option value="DRF API design">DRF API design</option>
                <option value="Testing">Testing</option>
                <option value="Django ORM">Django ORM</option>
                <option value="Performance">Performance</option>
                <option value="DevOps">DevOps</option>
              </select>
            </div>

            <div className="admin-form-group">
              <label className="admin-form-label" htmlFor="task-rubric-select">
                Rubric
              </label>
              <select
                id="task-rubric-select"
                className="admin-form-select"
                value={rubric}
                onChange={(e) => setRubric(e.target.value)}
              >
                <option value="">Select rubric</option>
                {rubrics.map((item) => <option key={item.id} value={item.id} disabled={item.status !== 'ACTIVE'}>{item.name}{item.status === 'ACTIVE' ? ' (live)' : ' (draft)'}</option>)}
              </select>
            </div>
          </div>

          {/* Assign to Batches */}
          <div className="admin-form-group">
            <label className="admin-form-label">
              Assign to batches
            </label>
            <div className="admin-batches-selector-grid">
              {batchOptions.map((b) => {
                const isSelected = selectedBatches.includes(b.id);
                return (
                  <div
                    key={b.id}
                    className={`admin-batch-select-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleToggleBatch(b.id)}
                  >
                    <div className="admin-custom-checkbox">
                      {isSelected && (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </div>
                    <div className="admin-batch-card-info">
                      <span className="admin-batch-card-title">{b.name}</span>
                      <span className="admin-batch-card-subtext">{b.subtext}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3-Column Row: Due Date, Due Time, Questions Per Trainee */}
          <div className="admin-form-row-3col">
            <div className="admin-form-group">
              <label className="admin-form-label" htmlFor="task-due-date">
                Due date
              </label>
              <div className="admin-input-with-icon">
                <input
                  id="task-due-date"
                  type="date"
                  className="admin-form-input"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  placeholder="3 Oct 2026"
                />
                <span className="admin-input-icon-right">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                </span>
              </div>
            </div>

            <div className="admin-form-group">
              <label className="admin-form-label" htmlFor="task-due-time">
                Due time
              </label>
              <input
                id="task-due-time"
                type="text"
                className="admin-form-input"
                value={dueTime}
                onChange={(e) => setDueTime(e.target.value)}
                placeholder="11:59 pm"
              />
            </div>

            <div className="admin-form-group">
              <label className="admin-form-label" htmlFor="task-questions-count">
                Questions per trainee
              </label>
              <select
                id="task-questions-count"
                className="admin-form-select"
                value={questionsCount}
                onChange={(e) => setQuestionsCount(e.target.value)}
              >
                <option value="4">4</option>
                <option value="5">5</option>
                <option value="6">6</option>
                <option value="8">8</option>
                <option value="10">10</option>
              </select>
            </div>
          </div>

          {/* Checkbox Toggles Row */}
          <div className="admin-checkbox-toggles-row">
            <label 
              className="admin-toggle-checkbox-item"
              onClick={() => setRequirePdf(!requirePdf)}
            >
              <div className="admin-custom-checkbox" style={{
                backgroundColor: requirePdf ? '#2563eb' : '#ffffff',
                borderColor: requirePdf ? '#2563eb' : '#64748b',
                color: '#ffffff'
              }}>
                {requirePdf && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              <span>Require a learning PDF</span>
            </label>

            <label 
              className="admin-toggle-checkbox-item"
              onClick={() => setAllowResubmission(!allowResubmission)}
            >
              <div className="admin-custom-checkbox" style={{
                backgroundColor: allowResubmission ? '#2563eb' : '#ffffff',
                borderColor: allowResubmission ? '#2563eb' : '#64748b',
                color: '#ffffff'
              }}>
                {allowResubmission && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              <span>Allow resubmission until due</span>
            </label>
          </div>

          {/* Action Buttons */}
          <div className="admin-create-task-buttons-row">
            <button
              type="submit"
              className="admin-btn-assign-primary"
            >
              Assign to {totalTrainees} trainees
            </button>
            <button
              type="button"
              className="admin-btn-save-draft"
              onClick={handleSaveDraft}
            >
              Save as draft
            </button>
          </div>
        </form>

        {/* Right: Preview & Information Sidebar */}
        <aside className="admin-create-task-sidebar">
          {/* Card 1: What trainees will see */}
          <div className="admin-sidebar-preview-card">
            <h3 className="admin-sidebar-card-title">What trainees will see</h3>
            
            <div className="admin-trainee-preview-box">
              <div className="admin-trainee-preview-top-row">
                <h4 className="admin-trainee-preview-task-title">
                  {taskTitle || 'Untitled Task'}
                </h4>
                <span className="admin-trainee-preview-status-pill">
                  Not submitted
                </span>
              </div>
              <div className="admin-trainee-preview-bottom-row">
                <span>{skill}</span>
                <span>{formattedDuePreview()}</span>
              </div>
            </div>
          </div>

          {/* Card 2: When you assign */}
          <div className="admin-sidebar-preview-card">
            <h3 className="admin-sidebar-card-title">When you assign</h3>
            
            <div className="admin-assign-checklist">
              <div className="admin-assign-checklist-item">
                <span className="admin-assign-check-icon">✓</span>
                <span>
                  <strong>{totalTrainees} trainees</strong> can access the task once it is activated
                </span>
              </div>
              <div className="admin-assign-checklist-item">
                <span className="admin-assign-check-icon">✓</span>
                <span>
                  {selectedBatches.length > 1
                    ? `TAs of both batches can review`
                    : selectedBatches.length === 1
                    ? `TA of the assigned batch can review`
                    : `TAs will review once assigned`}
                </span>
              </div>
              <div className="admin-assign-checklist-item">
                <span className="admin-assign-check-icon">✓</span>
                  <span>The selected rubric is fixed when this task is assigned</span>
              </div>
              <div className="admin-assign-checklist-item">
                <span className="admin-assign-check-icon">✓</span>
                <span>You can extend the due date later</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
