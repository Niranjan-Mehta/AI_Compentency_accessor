import React from 'react';
import './AdminOverviewView.css';
import { useApp } from '../../context/AppContext.jsx';

export const AdminOverviewView = ({ onNavigateTab }) => {
  const { currentUser, batches, tasks, reports, assessments } = useApp();
  const published = Object.values(reports).filter((item) => item.status === 'PUBLISHED');
  const pending = Object.values(reports).filter((item) => item.status === 'DRAFT');
  const traineeCount = batches.reduce((sum, batch) => sum + (batch.trainee_count || 0), 0);
  return <div className="admin-overview-container">
    <div className="admin-overview-header-row"><div className="admin-overview-title-group"><h1 className="admin-overview-title">Welcome, {currentUser?.name}</h1><p className="admin-overview-subtitle">Your live workspace summary.</p></div>
      <div className="admin-overview-actions"><button className="admin-btn-primary" onClick={() => onNavigateTab('create-task')}>Create task</button><button className="admin-btn-secondary" onClick={() => onNavigateTab('batches')}>Manage batches</button></div></div>
    <div className="admin-stat-cards-grid">{[['Batches', batches.length], ['Trainees', traineeCount], ['Assessments', assessments.length], ['Reports to publish', pending.length]].map(([label, value]) => <div className="admin-stat-card" key={label}><div className="admin-stat-card-title">{label}</div><div className="admin-stat-card-value">{value}</div><div className="admin-stat-card-desc">Live backend records</div></div>)}</div>
    <div className="admin-overview-columns-grid"><section className="admin-section-box"><h2 className="admin-section-heading">Your batches</h2>{batches.length ? batches.map((batch) => <button key={batch.id} className="admin-batch-card-item" onClick={() => onNavigateTab('batches')}><strong>{batch.name}</strong><span className="admin-batch-subtitle">{batch.trainee_count} trainees · {batch.ta_count} TAs</span></button>) : <p>No batches yet. Create one in Batches.</p>}</section>
      <section className="admin-section-box"><h2 className="admin-section-heading">Workflow</h2><p>{tasks.length} tasks · {pending.length} prepared reports · {published.length} published reports</p><button className="admin-btn-primary" onClick={() => onNavigateTab('reports')}>Review assessments and reports</button></section></div>
  </div>;
};
