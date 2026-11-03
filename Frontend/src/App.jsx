import React, { useEffect, useState } from 'react';
import { AppProvider, useApp } from './context/AppContext.jsx';
import { Header } from './components/Header/Header.jsx';
import { DashboardView } from './components/DashboardView/DashboardView.jsx';
import { SubmitWorkView } from './components/SubmitWorkView/SubmitWorkView.jsx';
import { CodeQuestionsView } from './components/CodeQuestionsView/CodeQuestionsView.jsx';
import { ReportDetailView } from './components/ReportDetailView/ReportDetailView.jsx';
import { LoginView } from './components/LoginView/LoginView.jsx';
import { AdminHeader } from './admin/AdminHeader/AdminHeader.jsx';
import { AdminOverviewView } from './admin/AdminOverviewView/AdminOverviewView.jsx';
import { AdminBatchesView } from './admin/AdminBatchesView/AdminBatchesView.jsx';
import { AdminCreateTaskView } from './admin/AdminCreateTaskView/AdminCreateTaskView.jsx';
import { AdminRubricsView } from './admin/AdminRubricsView/AdminRubricsView.jsx';
import { AdminReportsView } from './admin/AdminReportsView/AdminReportsView.jsx';
import { AdminAuditLogView } from './admin/AdminAuditLogView/AdminAuditLogView.jsx';
import { TAAssessmentView } from './components/TAAssessmentView/TAAssessmentView.jsx';
import { EvaluationFeedbackView } from './components/EvaluationFeedbackView/EvaluationFeedbackView.jsx';

function MainApp() {
  const { currentUser, authReady, loading, appError, notice, setNotice, logout } = useApp();
  const [currentView, setCurrentView] = useState('dashboard');
  const [facultyTab, setFacultyTab] = useState('overview');

  useEffect(() => {
    if (!currentUser) return;
    setCurrentView('dashboard');
    setFacultyTab('overview');
  }, [currentUser?.id, currentUser?.role]);

  if (!authReady) {
    return <div className="main-wrapper"><p className="page-subtitle">Restoring your session…</p></div>;
  }
  if (!currentUser) return <LoginView />;

  if (currentUser.role === 'FACULTY') {
    return (
      <div className="app-container" style={{ minHeight: '100vh', backgroundColor: '#f0f4f8' }}>
        <AdminHeader activeTab={facultyTab} onSelectTab={setFacultyTab} onLogout={logout} />
        {(appError || notice) && (
          <div role="status" style={{ margin: '14px auto', maxWidth: 1200, padding: '12px 18px', borderRadius: 8, background: appError ? '#fef2f2' : '#ecfdf5', color: appError ? '#991b1b' : '#065f46' }}>
            {appError || notice} <button type="button" onClick={() => setNotice('')} style={{ float: 'right' }}>Dismiss</button>
          </div>
        )}
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {facultyTab === 'overview' && <AdminOverviewView onNavigateTab={setFacultyTab} />}
          {facultyTab === 'batches' && <AdminBatchesView onNavigateTab={setFacultyTab} />}
          {facultyTab === 'create-task' && <AdminCreateTaskView onNavigateTab={setFacultyTab} />}
          {facultyTab === 'rubrics' && <AdminRubricsView onNavigateTab={setFacultyTab} />}
          {facultyTab === 'reports' && <AdminReportsView onNavigateTab={setFacultyTab} />}
          {facultyTab === 'audit-log' && <AdminAuditLogView onNavigateTab={setFacultyTab} />}
        </main>
      </div>
    );
  }

  if (currentUser.role === 'TA') {
    return (
      <div className="app-container" style={{ minHeight: '100vh', backgroundColor: '#f0f4f8' }}>
        <AdminHeader activeTab="review" onSelectTab={() => {}} onLogout={logout} role="TA" />
        {(appError || notice) && <div role="status" style={{ margin: '14px auto', maxWidth: 1200, padding: '12px 18px', borderRadius: 8, background: appError ? '#fef2f2' : '#ecfdf5', color: appError ? '#991b1b' : '#065f46' }}>{appError || notice}</div>}
        <TAAssessmentView />
      </div>
    );
  }

  return (
    <div className="app-container">
      <Header currentView={currentView} onNavigate={setCurrentView} onLogout={logout} />
      {(appError || notice) && <div role="status" style={{ margin: '12px auto', maxWidth: 1180, padding: '10px 16px', borderRadius: 8, background: appError ? '#fef2f2' : '#ecfdf5', color: appError ? '#991b1b' : '#065f46' }}>{appError || notice}</div>}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {currentView === 'dashboard' && <DashboardView onNavigate={setCurrentView} />}
        {currentView === 'submit-work' && <SubmitWorkView onNavigate={setCurrentView} />}
        {currentView === 'code-questions' && <CodeQuestionsView onNavigate={setCurrentView} />}
        {currentView === 'report-detail' && <ReportDetailView onNavigate={setCurrentView} />}
        {currentView === 'evaluation-feedback' && <EvaluationFeedbackView onNavigate={setCurrentView} />}
      </main>
    </div>
  );
}

export default function App() {
  return <AppProvider><MainApp /></AppProvider>;
}
