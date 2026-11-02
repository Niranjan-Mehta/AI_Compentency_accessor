import React, { useEffect, useState } from 'react';
import './CodeQuestionsView.css';
import { useApp } from '../../context/AppContext.jsx';

export const CodeQuestionsView = ({ onNavigate }) => {
  const {
    tasks,
    activeTaskId,
    getQuestionsForTask,
    updateQuestion,
    saveQuestionDraft,
    submitAllQuestions,
    loadQuestionsForTask,
    setAppError,
  } = useApp();

  const currentTask = tasks.find((t) => t.id === activeTaskId) || tasks.find((t) => t.status === 'questions-ready');
  const questions = getQuestionsForTask(currentTask?.id) || [];

  // Default to question 2 (index 1) or first unsaved
  const [currentIndex, setCurrentIndex] = useState(() => {
    const firstUnsavedIdx = questions.findIndex((q) => !q.isSaved);
    return firstUnsavedIdx !== -1 ? firstUnsavedIdx : 0;
  });

  const [busy, setBusy] = useState(false);
  useEffect(() => { if (currentTask?.submission && !questions.length) loadQuestionsForTask(currentTask.id).catch((error) => setAppError(error.message)); }, [currentTask?.id]);

  const currentQ = questions[currentIndex] || questions[0];
  if (!currentTask) return <div className="main-wrapper"><h1 className="page-title">Questions</h1><p>No generated questions are available yet.</p><button className="btn-secondary-cancel" onClick={() => onNavigate('dashboard')}>Back to dashboard</button></div>;
  if (!currentQ) return <div className="main-wrapper"><p>Loading generated questions…</p></div>;

  const handleAnswerChange = (val) => {
    updateQuestion(currentTask.id, currentQ.id, {
      answer: val
    });
  };

  const handleSaveDraft = async () => {
    const currentAnswer = currentQ.answer ? currentQ.answer.trim() : '';
    setBusy(true); try { await saveQuestionDraft(currentTask.id, currentQ.id, currentAnswer); } catch (error) { setAppError(error.message); } finally { setBusy(false); }
  };

  const handleSaveAndNext = async () => {
    const currentAnswer = currentQ.answer ? currentQ.answer.trim() : '';
    setBusy(true); try { await saveQuestionDraft(currentTask.id, currentQ.id, currentAnswer); } catch (error) { setAppError(error.message); setBusy(false); return; } finally { setBusy(false); }

    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const completedCount = questions.filter((q) => q.isSaved === true).length;

  const handleSubmitAll = async () => {
    if (completedCount !== questions.length) { setAppError(`Save all ${questions.length} answers before submitting (${completedCount} saved).`); return; }
    setBusy(true); try { await submitAllQuestions(currentTask.id); onNavigate('dashboard'); } catch (error) { setAppError(error.message); } finally { setBusy(false); }
  };

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
        <span className="breadcrumb-current">{currentTask.name}</span>
      </nav>

      {/* Header with counter */}
      <div className="question-page-header">
        <h1 className="page-title" style={{ margin: 0 }}>Questions about your code</h1>
          <span className="question-counter-indicator">Question {currentIndex + 1} of {questions.length}</span>
      </div>

      {/* 6-Step Multi-segment Progress Bar: green for saved questions */}
      <div className="question-progress-multi">
        {questions.map((q, idx) => {
          let stateClass = 'upcoming';
          if (q.isSaved === true) {
            stateClass = idx === currentIndex ? 'completed active-completed' : 'completed';
          } else if (idx === currentIndex) {
            stateClass = 'current';
          }
          return (
            <div 
              key={q.id} 
              className={`q-progress-bar-seg ${stateClass}`}
              title={`Question ${q.id}: ${q.title} (${q.isSaved ? 'Saved' : idx === currentIndex ? 'Current' : 'Unsaved'})`}
              style={{ cursor: 'pointer' }}
              onClick={() => setCurrentIndex(idx)}
            ></div>
          );
        })}
      </div>

      {/* Two Column Layout */}
      <div className="two-column-layout">
        {/* Left Column: Question, Code Snippet, Answer */}
        <div>
          {/* Question Meta Tags */}
          <div className="question-meta-tags">
            {currentQ.tags.map((tag, i) => (
              <span key={i} className="tag-pill-outline">{tag}</span>
            ))}
          </div>

          {/* Question Prompt */}
          <h2 className="question-prompt-text">{currentQ.prompt}</h2>

          {/* Code Snippet Window */}
          <div className="code-snippet-window">
            <div className="code-snippet-header">
              <span>{currentQ.codeFile}</span>
              <span>line {currentQ.codeLine}</span>
            </div>
            <div className="code-snippet-body">
              {currentQ.codeLines.map((line) => (
                <div 
                  key={line.num} 
                  className={`code-line ${line.highlighted ? 'highlighted' : ''}`}
                >
                  <span className="code-line-num">{line.num}</span>
                  <span className="code-line-content">{line.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Answer Section */}
          <div className="answer-section">
            <label className="form-label" htmlFor="answer-textarea">
              Your answer
            </label>
            <textarea
              id="answer-textarea"
              className="answer-textarea-box"
              value={currentQ.answer || ''}
              onChange={(e) => handleAnswerChange(e.target.value)}
              placeholder="Type your explanation here..."
              maxLength={2000}
            />

            <div className="answer-status-bar">
              <div className="draft-saved-text">
                {currentQ.isSaved ? (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span style={{ color: '#16a34a', fontWeight: 600 }}>Draft saved at {currentQ.savedTime || '10:42 am'}</span>
                  </>
                ) : (
                  <>
                    <span style={{ color: '#64748b', fontSize: '12px' }}>
                      {currentQ.answer && currentQ.answer.trim().length > 0 ? 'Unsaved draft — click Save draft or Save and next' : 'Not saved yet'}
                    </span>
                    {currentQ.answer && currentQ.answer.trim().length > 0 && (
                      <button 
                        type="button" 
                        onClick={handleSaveDraft}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#0284c7',
                          fontWeight: 600,
                          fontSize: '12px',
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          marginLeft: '6px'
                        }}
                      >
                        Save now
                      </button>
                    )}
                  </>
                )}
              </div>
              <div style={{ color: '#64748b' }}>
                {(currentQ.answer || '').length} / 2000 characters
              </div>
            </div>

            {/* Previous and Save/Next buttons */}
            <div className="q-nav-buttons-row">
              <button 
                type="button" 
                className="btn-secondary-cancel"
                onClick={handlePrevious}
                disabled={currentIndex === 0}
                style={{ opacity: currentIndex === 0 ? 0.5 : 1 }}
              >
                &lt; Previous
              </button>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button disabled={busy}
                  type="button" 
                  className="btn-secondary-cancel"
                  onClick={handleSaveDraft}
                >
                  Save draft
                </button>

                <button disabled={busy}
                  type="button" 
                  className="btn-primary-submit"
                  onClick={handleSaveAndNext}
                >
                  {currentIndex === questions.length - 1 ? 'Save answer' : 'Save and next'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sidebar: All questions list - GREEN TICK ONLY FOR SAVED ONES */}
        <div className="side-column">
          <div className="questions-menu-card">
            <h3 className="questions-menu-title">All questions</h3>
            <div className="questions-list">
              {questions.map((q, idx) => {
                const isActive = idx === currentIndex;
                const isSaved = q.isSaved === true;

                return (
                  <button
                    key={q.id}
                    type="button"
                    className={`question-nav-item ${isActive ? 'active' : ''}`}
                    onClick={() => setCurrentIndex(idx)}
                  >
                    {/* ONLY SHOW GREEN TICK IF IS_SAVED IS TRUE */}
                    {isSaved ? (
                      <div className="q-status-icon-circle checked" title="Saved">✓</div>
                    ) : (
                      <div 
                        className={`q-status-icon-circle ${isActive ? 'current-num' : 'pending-num'}`}
                        title={isActive ? 'Current question' : 'Unsaved'}
                      >
                        {q.id}
                      </div>
                    )}
                    <span>{q.title}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Info Card */}
          <div className="info-banner-card">
            <div className="info-icon-circle">i</div>
            <div className="info-banner-text">
              <strong>Answer all {questions.length} to submit</strong><br />
              You can go in any order. Nothing is sent until you press Submit all answers. {completedCount} of {questions.length} done.
            </div>
          </div>

          {/* Submit all answers */}
          <button 
            type="button" 
            className="btn-submit-all-answers"
            onClick={handleSubmitAll}
            disabled={busy || completedCount !== questions.length}
          >
            Submit all answers
          </button>
        </div>
      </div>
    </div>
  );
};
