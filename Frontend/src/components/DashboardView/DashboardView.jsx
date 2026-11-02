import React, { useState } from 'react';
import './DashboardView.css';
import { useApp } from '../../context/AppContext.jsx';

export const DashboardView = ({ onNavigate }) => {
  const [filter, setFilter] = useState('all');
  const {
    currentUser,
    tasks,
    todoTasks,
    doneTasks,
    todoCount,
    doneCount,
    dueTomorrowCount,
    publishedCount,
    averageScore,
    setActiveTaskId,
    setActiveReportId,
    setActiveAssessmentRunId,
    setSubmissionModalTask,
    startQuestionGeneration,
    startProcessing,
    loadQuestionsForTask,
    refreshWorkspace,
    setAppError
  } = useApp();

  const filteredTasks = tasks.filter((task) => {
    if (filter === 'todo') {
      return task.status === 'not-submitted' || task.status === 'questions-ready';
    }
    if (filter === 'done') {
      return task.status === 'processing' || task.status === 'under-review' || task.status === 'published';
    }
    return true;
  });

  const handleAction = async (task) => {
    setAppError('');
    if (task.actionType === 'submit') {
      setActiveTaskId(task.id);
      onNavigate('submit-work');
    } else if (task.actionType === 'questions') {
      setActiveTaskId(task.id);
      try {
        if (task.submission?.status === 'QUESTIONS_READY' && task.assessmentRunId) { await loadQuestionsForTask(task.id); onNavigate('code-questions'); }
        else {
          await startQuestionGeneration(task.id);
          await refreshWorkspace();
        }
      } catch (error) { setAppError(error.message); }
    } else if (task.actionType === 'view-report') {
      setActiveReportId(task.reportId);
      onNavigate('report-detail');
    } else if (task.actionType === 'view-submission') {
      if (task.assessmentRunId) {
        setActiveAssessmentRunId(task.assessmentRunId);
        onNavigate('evaluation-feedback');
      } else setSubmissionModalTask(task);
    } else if (task.actionType === 'retry-processing') {
      try { await startProcessing(task.id); } catch (error) { setAppError(error.message); }
    } else if (task.actionType === 'retry-evaluation') {
      try { await loadQuestionsForTask(task.id); onNavigate('code-questions'); } catch (error) { setAppError(error.message); }
    } else if (task.actionType === 'processing-time') {
      try { await refreshWorkspace(); } catch (error) { setAppError(error.message); }
    }
  };

  return (
    <div className="main-wrapper">
      {/* Page Heading */}
      <div className="page-heading-group">
        <h1 className="page-title">Good morning, {currentUser.name}</h1>
        <p className="page-subtitle">
          {todoCount > 0 
            ? `You have ${todoCount} task${todoCount > 1 ? 's' : ''} that need${todoCount === 1 ? 's' : ''} you this week.` 
            : 'All caught up! No pending tasks requiring action.'}
        </p>
      </div>

      {/* Top Stat Cards Grid */}
      <div className="stat-cards-grid">
        {/* Card 1: Tasks to do */}
        <div className="stat-card">
          <div className="stat-card-title">Tasks to do</div>
          <div className="stat-card-value">{todoCount}</div>
          <div className="stat-card-desc">
            {dueTomorrowCount > 0 ? `${dueTomorrowCount} due tomorrow` : 'No urgent deadlines'}
          </div>
        </div>

        {/* Card 2: Average score */}
        <div className="stat-card">
          <div className="stat-card-title">Average score</div>
          <div className="stat-card-value">{averageScore}%</div>
          <div className="stat-card-desc">
            Across {publishedCount} published report{publishedCount !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Card 3: Current level */}
        <div className="stat-card">
          <div className="stat-card-title">Current level</div>
          <div className="stat-card-value">{currentUser.level || '—'}</div>
          <div className="stat-card-desc">
            {currentUser.levelName || 'Not yet rated'}. {currentUser.nextLevel ? `Next: ${currentUser.nextLevel}` : ''}
          </div>
          <div className="level-segments-bar">
            {Array.from({ length: currentUser.totalSegments || 4 }).map((_, idx) => (
              <div
                key={idx}
                className={`level-segment ${idx < currentUser.completedSegments ? 'filled' : 'empty'}`}
                title={`Level ${idx + 1}`}
              ></div>
            ))}
          </div>
        </div>
      </div>

      {/* Section Box: Your tasks */}
      <div className="section-card">
        <div className="section-header-row">
          <h2 className="section-heading">Your tasks</h2>
          
          <div className="filter-tabs-pills">
            <button 
              className={`filter-pill-btn ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All ({tasks.length})
            </button>
            <button 
              className={`filter-pill-btn ${filter === 'todo' ? 'active' : ''}`}
              onClick={() => setFilter('todo')}
            >
              To do ({todoTasks.length})
            </button>
            <button 
              className={`filter-pill-btn ${filter === 'done' ? 'active' : ''}`}
              onClick={() => setFilter('done')}
            >
              Done ({doneTasks.length})
            </button>
          </div>
        </div>

        {/* Tasks Data Table */}
        <div className="tasks-table-container">
          <table className="tasks-table">
            <thead>
              <tr>
                <th style={{ width: '28%' }}>Task</th>
                <th style={{ width: '22%' }}>Skill</th>
                <th style={{ width: '18%' }}>Due</th>
                <th style={{ width: '17%' }}>Status</th>
                <th style={{ width: '15%', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
                {filteredTasks.map((task) => (
                <tr key={task.id}>
                  {/* Task name */}
                  <td>
                    <span className="task-name-text">{task.name}</span>
                  </td>

                  {/* Skill */}
                  <td>
                    <span className="skill-name-text">{task.skill}</span>
                  </td>

                  {/* Due */}
                  <td>
                    {task.dueBadge ? (
                      <span className="badge-warning-amber">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                          <line x1="12" y1="9" x2="12" y2="13"></line>
                          <line x1="12" y1="17" x2="12.01" y2="17"></line>
                        </svg>
                        {task.dueText}
                      </span>
                    ) : (
                      <span className="due-date-text">{task.dueText}</span>
                    )}
                  </td>

                  {/* Status */}
                  <td>
                    {task.status === 'not-submitted' && (
                      <span className="status-pill not-submitted">
                        {task.statusLabel}
                      </span>
                    )}

                    {task.status === 'questions-ready' && (
                      <span className="status-pill questions-ready">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="16" x2="12" y2="12"></line>
                          <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                        {task.statusLabel}
                      </span>
                    )}

                    {task.status === 'processing' && (
                      <span 
                        className="status-pill processing"
                        title="Refresh processing status"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleAction(task)}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                          <path d="M3 3v5h5"></path>
                          <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path>
                          <path d="M16 21h5v-5"></path>
                        </svg>
                        {task.statusLabel}
                      </span>
                    )}

                    {task.status === 'under-review' && (
                      <span className="status-pill under-review">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        {task.statusLabel}
                      </span>
                    )}

                    {task.status === 'published' && (
                      <span className="status-pill published">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        {task.statusLabel}
                      </span>
                    )}
                  </td>

                  {/* Action */}
                  <td style={{ textAlign: 'right' }}>
                    {task.actionType === 'submit' && (
                      <button 
                        className="btn-table-action-primary"
                        onClick={() => handleAction(task)}
                      >
                        Submit
                      </button>
                    )}

                    {task.actionType === 'questions' && (
                      <button 
                        className="btn-table-action-secondary"
                        onClick={() => handleAction(task)}
                      >
                        Answer questions
                      </button>
                    )}

                    {task.actionType === 'processing-time' && (
                      <span 
                        className="table-action-text" 
                        title="Refresh processing status"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleAction(task)}
                      >
                        {task.actionLabel}
                      </span>
                    )}

                    {task.actionType === 'view-submission' && (
                      <button 
                        className="table-link-action"
                        onClick={() => handleAction(task)}
                      >
                        {task.actionLabel}
                      </button>
                    )}

                    {task.actionType === 'view-report' && (
                      <button 
                        className="table-link-action"
                        onClick={() => handleAction(task)}
                      >
                        {task.actionLabel}
                      </button>
                    )}

                    {task.actionType === 'retry-processing' && (
                      <button className="btn-table-action-secondary" onClick={() => handleAction(task)}>{task.actionLabel}</button>
                    )}

                    {task.actionType === 'retry-evaluation' && (
                      <button className="btn-table-action-secondary" onClick={() => handleAction(task)}>{task.actionLabel}</button>
                    )}
                  </td>
                </tr>
              ))}
                {filteredTasks.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center', padding: 30, color: '#64748b' }}>{tasks.length ? 'No tasks match this filter.' : 'No tasks have been assigned to you yet.'}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
