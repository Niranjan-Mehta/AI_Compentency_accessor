import React, { useState, useMemo, useEffect } from 'react';
import './AdminBatchesView.css';
import { useApp } from '../../context/AppContext.jsx';

export const AdminBatchesView = ({ onNavigateTab }) => {
  const { batches, tasks, api, setAppError, setNotice, refreshWorkspace } = useApp();
  const adminBatches = batches.map((b) => ({ ...b, traineeCount: b.trainee_count || 0, taName: b.tas?.map((ta) => ta.first_name || ta.username).join(', ') || 'Unassigned', completedTasks: tasks.filter((t) => t.status === 'COMPLETED' && t.batches?.some((x) => x.id === b.id)).length, totalTasks: tasks.filter((t) => t.batches?.some((x) => x.id === b.id)).length, startDate: b.start_date || '—', endDate: b.end_date || '—', status: b.is_active ? 'Active' : 'Inactive' }));
  const [selectedBatchId, setSelectedBatchId] = useState('');
  const [activeSubtab, setActiveSubtab] = useState('trainees'); // 'trainees' | 'tasks' | 'settings'

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState('All');

  // Trainees state
  const [trainees, setTrainees] = useState([]);
  const [page, setPage] = useState(1);
  const pageSize = 6;

  // Selected trainee modal state
  const [selectedTrainee, setSelectedTrainee] = useState(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('TRAINEE');
  const [batchNameEdit, setBatchNameEdit] = useState('');
  const [startDateEdit, setStartDateEdit] = useState('');
  const [endDateEdit, setEndDateEdit] = useState('');

  const currentBatch = adminBatches.find((b) => String(b.id) === String(selectedBatchId)) || adminBatches[0] || { id: '', name: 'Batches', description: '', traineeCount: 0, taName: 'Unassigned', completedTasks: 0, totalTasks: 0, startDate: '—', endDate: '—', status: 'Inactive' };
  useEffect(() => { if (!selectedBatchId && adminBatches.length) setSelectedBatchId(String(adminBatches[0].id)); }, [selectedBatchId, batches]);
  useEffect(() => {
    if (!currentBatch.id) return;
    api.all(`/batches/${currentBatch.id}/trainees/`).then((rows) => setTrainees(rows.map((u) => { const total = tasks.filter((t) => t.batches?.some((b) => b.id === currentBatch.id)).length; return { ...u, id: u.id, batchId: currentBatch.id, name: [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username, employeeId: u.employee_id || '—', level: 'Not rated', lastActiveStatus: 'normal', tasksDoneNum: 0, tasksTotalNum: total, tasksDone: `0 of ${total}`, avgScore: '—', lastActive: '—' }; }))).catch((error) => setAppError(error.message));
  }, [currentBatch.id, api, setAppError, tasks]);
  const batchTasksList = tasks.filter((task) => task.batches?.some((batch) => batch.id === currentBatch.id)).map((task) => ({ id: task.id, batchId: currentBatch.id, name: task.title, skill: task.skill, dueDate: task.due_date ? new Date(task.due_date).toLocaleDateString() : 'No due date', status: task.status, submissionsCount: 0, publishedReports: 0, avgScore: null }));

  // Filter trainees
  const filteredTrainees = useMemo(() => {
    return trainees.filter((tr) => {
      if (String(tr.batchId) !== String(currentBatch.id)) return false;
      
      const matchesSearch = 
        tr.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tr.employeeId.includes(searchQuery);

      if (!matchesSearch) return false;

      if (levelFilter === 'All') return true;
      if (levelFilter === 'Not rated') return tr.level === 'Not rated';
      return tr.level === levelFilter;
    });
  }, [trainees, currentBatch, searchQuery, levelFilter]);

  // Paginated trainees
  const totalTrainees = filteredTrainees.length;
  const paginatedTrainees = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredTrainees.slice(start, start + pageSize);
  }, [filteredTrainees, page]);

  const totalPages = Math.ceil(totalTrainees / pageSize) || 1;

  // Count inactive trainees that need a nudge
  const inactiveCount = trainees.filter(
    (t) => t.batchId === currentBatch.id && t.lastActiveStatus === 'warning-inactive'
  ).length;

  const handleNudgeTrainee = (trainee) => {
    setNotice('Reminder delivery is not configured. No message was sent.');
    setSelectedTrainee(null);
  };

  const handleNudgeAll = () => {
    setNotice('Reminder delivery is not configured. No messages were sent.');
  };

  const handleSendInvite = (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) {
      alert('Please enter an email address.');
      return;
    }
    api.request('/auth/invite/', { method: 'POST', body: JSON.stringify({ email: inviteEmail, role: inviteRole, batch_id: currentBatch.id, send_email: true }) }).then(async () => { setNotice(`${inviteRole === 'TA' ? 'TA' : 'Trainee'} invitation created for ${inviteEmail}.`); await refreshWorkspace(); setShowInviteModal(false); setInviteEmail(''); }).catch((error) => setAppError(error.message));
  };

  return (
    <div className="admin-batches-container">
      {/* Breadcrumb Navigation: Batches > DRF Batch 12 */}
      <nav className="admin-breadcrumb-nav">
        <span 
          className="admin-breadcrumb-link"
          onClick={() => onNavigateTab ? onNavigateTab('overview') : null}
        >
          Batches
        </span>
        <span className="admin-breadcrumb-separator">&gt;</span>
        <span className="admin-breadcrumb-current">{currentBatch.name}</span>

        {/* Batch switcher dropdown if faculty has multiple batches */}
        <select
          value={selectedBatchId}
          onChange={(e) => {
            setSelectedBatchId(e.target.value);
            setPage(1);
          }}
          className="admin-filter-dropdown"
          style={{ marginLeft: 'auto', padding: '3px 8px', fontSize: '12px' }}
        >
          {adminBatches.map((b) => (
            <option key={b.id} value={b.id}>Switch: {b.name}</option>
          ))}
        </select>
      </nav>

      {/* Batch Header Area */}
      <div className="admin-batch-header-group">
        <div>
          <div className="admin-batch-title-row">
            <h1 className="admin-batch-main-title">{currentBatch.name}</h1>
            <span className="admin-batch-status-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              Active
            </span>
          </div>
          <p className="admin-batch-meta-desc">
            {currentBatch.traineeCount} trainees. TA: {currentBatch.taName}. Started {currentBatch.startDate}, ends {currentBatch.endDate}.
          </p>
        </div>

        <div className="admin-batch-header-actions">
          <button 
            type="button" 
            className="admin-btn-outline"
            onClick={() => setShowInviteModal(true)}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="4" width="20" height="16" rx="2"></rect>
              <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
            </svg>
            Invite trainees
          </button>

          <button 
            type="button" 
            className="admin-btn-dark"
            onClick={() => onNavigateTab ? onNavigateTab('create-task') : alert('Create task')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            Create task
          </button>
        </div>
      </div>

      {/* Sub-tabs: Trainees (30), Tasks (8), Settings */}
      <div className="admin-subtabs-bar">
        <button 
          className={`admin-subtab-btn ${activeSubtab === 'trainees' ? 'active' : ''}`}
          onClick={() => setActiveSubtab('trainees')}
        >
          Trainees ({currentBatch.traineeCount})
        </button>
        
        <button 
          className={`admin-subtab-btn ${activeSubtab === 'tasks' ? 'active' : ''}`}
          onClick={() => setActiveSubtab('tasks')}
        >
          Tasks ({currentBatch.totalTasks})
        </button>

        <button 
          className={`admin-subtab-btn ${activeSubtab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveSubtab('settings')}
        >
          Settings
        </button>
      </div>

      {/* TAB 1: TRAINEES VIEW */}
      {activeSubtab === 'trainees' && (
        <>
          {/* Table Filters Row */}
          <div className="admin-table-filters-row">
            <div className="admin-filters-left">
              {/* Search input with magnifying glass */}
              <div className="admin-search-input-box">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"></circle>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <input 
                  type="text"
                  placeholder="Search by name or ID"
                  className="admin-search-input"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setPage(1);
                  }}
                />
              </div>

              {/* Level Filter Dropdown */}
              <select 
                className="admin-filter-dropdown"
                value={levelFilter}
                onChange={(e) => {
                  setLevelFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="All">Level: All</option>
                <option value="L1">Level: L1</option>
                <option value="L2">Level: L2</option>
                <option value="L3">Level: L3</option>
                <option value="L4">Level: L4</option>
                <option value="Not rated">Level: Not rated</option>
              </select>
            </div>

            {/* Inactive Nudge Banner Note */}
            <div className="admin-filters-right-note">
              <span>{inactiveCount} trainees need a nudge</span>
              {inactiveCount > 0 && (
                <button 
                  type="button" 
                  className="admin-btn-nudge-all"
                  onClick={handleNudgeAll}
                  title="Send reminder to all inactive trainees"
                >
                  Nudge all
                </button>
              )}
            </div>
          </div>

          {/* Trainees Data Table matching Image 2 */}
          <div className="admin-table-card">
            <table className="admin-data-table">
              <thead>
                <tr>
                  <th style={{ width: '22%' }}>Trainee</th>
                  <th style={{ width: '16%' }}>Employee ID</th>
                  <th style={{ width: '14%' }}>Tasks done</th>
                  <th style={{ width: '14%' }}>Avg score</th>
                  <th style={{ width: '15%' }}>Level</th>
                  <th style={{ width: '14%' }}>Last active</th>
                  <th style={{ width: '5%', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedTrainees.map((trainee) => (
                  <tr key={trainee.id}>
                    {/* Trainee Name */}
                    <td>
                      <span className="admin-trainee-name">{trainee.name}</span>
                    </td>

                    {/* Employee ID */}
                    <td>
                      <span className="admin-employee-id">{trainee.employeeId}</span>
                    </td>

                    {/* Tasks done */}
                    <td>
                      <span>{trainee.tasksDone}</span>
                    </td>

                    {/* Avg score */}
                    <td>
                      <span style={{ fontWeight: trainee.avgScoreNum ? 600 : 400 }}>
                        {trainee.avgScore}
                      </span>
                    </td>

                    {/* Level with 4-segment mini bar */}
                    <td>
                      <div className="admin-level-badge-cell">
                        {trainee.level !== 'Not rated' && (
                          <div className="admin-level-segments-track">
                            {[1, 2, 3, 4].map((seg) => (
                              <div 
                                key={seg}
                                className={`admin-mini-level-seg ${seg <= trainee.levelSegments ? 'filled' : 'empty'}`}
                              />
                            ))}
                          </div>
                        )}
                        <span className="admin-level-text-label">{trainee.level}</span>
                      </div>
                    </td>

                    {/* Last active status */}
                    <td>
                      {trainee.lastActiveStatus === 'warning-inactive' && (
                        <span className="admin-status-pill-warning">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                          </svg>
                          {trainee.lastActive}
                        </span>
                      )}

                      {trainee.lastActiveStatus === 'pending' && (
                        <span className="admin-status-pill-pending">
                          {trainee.lastActive}
                        </span>
                      )}

                      {trainee.lastActiveStatus === 'normal' && (
                        <span className="admin-last-active-normal">
                          {trainee.lastActive}
                        </span>
                      )}
                    </td>

                    {/* Action */}
                    <td style={{ textAlign: 'right' }}>
                      <button 
                        type="button" 
                        className="admin-link-action"
                        onClick={() => setSelectedTrainee(trainee)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}

                {paginatedTrainees.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                      No trainees found matching your filter criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Pagination Footer */}
            <div className="admin-table-footer-pagination">
              <span className="admin-pagination-info">
                Showing {totalTrainees === 0 ? 0 : (page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalTrainees)} of {totalTrainees}
              </span>

              <div className="admin-pagination-controls">
                <button 
                  type="button"
                  className="admin-btn-page"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  &lt; Previous
                </button>
                <button 
                  type="button"
                  className="admin-btn-page"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next &gt;
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* TAB 2: TASKS VIEW */}
      {activeSubtab === 'tasks' && (
        <div className="admin-batch-tasks-grid">
          {batchTasksList.map((task) => (
            <div key={task.id} className="admin-batch-task-card">
              <div>
                <div className="admin-batch-task-header">
                  <h3 className="admin-batch-task-name">{task.name}</h3>
                  <span style={{ 
                    fontSize: '11px', 
                    fontWeight: 700, 
                    color: task.status === 'Completed' ? '#15803d' : task.status === 'Reviewing' ? '#0284c7' : '#b45309',
                    backgroundColor: task.status === 'Completed' ? '#dcfce7' : task.status === 'Reviewing' ? '#eff6ff' : '#fef3c7',
                    padding: '2px 8px',
                    borderRadius: '4px'
                  }}>
                    {task.status}
                  </span>
                </div>
                <span className="admin-batch-task-skill">{task.skill}</span>
              </div>

              <div className="admin-batch-task-meta">
                <span>Due: {task.dueDate}</span>
                <span>{task.submissionsCount} submissions</span>
                {task.avgScore ? <span>Avg: {task.avgScore}%</span> : null}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 3: SETTINGS VIEW */}
      {activeSubtab === 'settings' && (
        <div style={{ background: '#ffffff', border: '1.5px solid var(--border-color, #60a5fa)', borderRadius: '8px', padding: '24px', maxWidth: '640px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#0f172a', margin: '0 0 16px 0' }}>Batch Settings</h2>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Batch Name</label>
              <input 
                type="text" 
                value={batchNameEdit}
                onChange={(e) => setBatchNameEdit(e.target.value)}
                placeholder={currentBatch.name}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border-color, #60a5fa)', borderRadius: '6px' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Assigned Teaching Assistant</label>
              <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
                <span>{currentBatch.taName}</span>
                {(currentBatch.tas || []).map((ta) => <button key={ta.id} type="button" className="btn-secondary-cancel" onClick={async () => { try { await api.request(`/batches/${currentBatch.id}/tas/`, {method:'DELETE',body:JSON.stringify({user_ids:[ta.id]})}); await refreshWorkspace(); setNotice(`${ta.first_name || ta.username} removed from this batch.`); } catch (error) { setAppError(error.message); } }}>Remove {ta.first_name || ta.username}</button>)}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Start Date</label>
                <input 
                  type="date" 
                  value={startDateEdit}
                  onChange={(e) => setStartDateEdit(e.target.value)}
                  placeholder={currentBatch.startDate}
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border-color, #60a5fa)', borderRadius: '6px' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>End Date</label>
                <input 
                  type="date" 
                  value={endDateEdit}
                  onChange={(e) => setEndDateEdit(e.target.value)}
                  placeholder={currentBatch.endDate}
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border-color, #60a5fa)', borderRadius: '6px' }}
                />
              </div>
            </div>

            <div style={{ marginTop: '10px' }}>
              <button 
                type="button" 
                className="admin-btn-dark"
                onClick={async () => { try { await api.request(`/batches/${currentBatch.id}/`, {method:'PATCH', body:JSON.stringify({name:batchNameEdit.trim() || currentBatch.name, ...(startDateEdit ? {start_date:startDateEdit} : {}), ...(endDateEdit ? {end_date:endDateEdit} : {})})}); await refreshWorkspace(); setNotice('Batch settings saved.'); setBatchNameEdit(''); } catch (error) { setAppError(error.message); } }}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trainee Details Modal */}
      {selectedTrainee && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-dialog">
            <div className="admin-modal-header">
              <h3 className="admin-modal-title">Trainee Profile: {selectedTrainee.name}</h3>
              <button 
                type="button" 
                className="admin-modal-close-btn"
                onClick={() => setSelectedTrainee(null)}
              >
                ✕
              </button>
            </div>

            <div className="admin-trainee-modal-body">
              <div className="admin-trainee-header-box">
                <div>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>{selectedTrainee.name}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>Employee ID: {selectedTrainee.employeeId} • {currentBatch.name}</div>
                </div>
                <div>
                  <span className="admin-level-text-label" style={{ background: '#eff6ff', border: '1px solid #bfdbfe', padding: '4px 10px', borderRadius: '4px' }}>
                    Current: {selectedTrainee.level}
                  </span>
                </div>
              </div>

              <div className="admin-trainee-stats-grid">
                <div className="admin-trainee-stat-item">
                  <div className="admin-trainee-stat-label">Tasks Completed</div>
                  <div className="admin-trainee-stat-val">{selectedTrainee.tasksDone}</div>
                </div>
                <div className="admin-trainee-stat-item">
                  <div className="admin-trainee-stat-label">Average Score</div>
                  <div className="admin-trainee-stat-val">{selectedTrainee.avgScore}</div>
                </div>
                <div className="admin-trainee-stat-item">
                  <div className="admin-trainee-stat-label">Last Activity</div>
                  <div className="admin-trainee-stat-val" style={{ fontSize: '13px', paddingTop: '4px' }}>{selectedTrainee.lastActive}</div>
                </div>
              </div>

              <p style={{ fontSize: '12.5px', color: '#475569', margin: '6px 0 0' }}>
                Assigned Teaching Assistant: <strong>{currentBatch.taName}</strong>. 
                Reports published: {selectedTrainee.tasksDoneNum} of {selectedTrainee.tasksTotalNum}.
              </p>
            </div>

            <div className="admin-modal-buttons-row">
              <button 
                type="button" 
                className="admin-btn-outline"
                onClick={() => setSelectedTrainee(null)}
              >
                Close
              </button>
              <button 
                type="button" 
                className="admin-btn-dark"
                onClick={() => handleNudgeTrainee(selectedTrainee)}
              >
                Send Nudge Alert
              </button>
              <button type="button" className="admin-btn-outline" onClick={async () => { try { await api.request(`/batches/${currentBatch.id}/trainees/`, {method:'DELETE',body:JSON.stringify({user_ids:[selectedTrainee.id]})}); await refreshWorkspace(); setSelectedTrainee(null); setNotice(`${selectedTrainee.name} removed from ${currentBatch.name}.`); } catch (error) { setAppError(error.message); } }}>Remove from batch</button>
            </div>
          </div>
        </div>
      )}

      {/* Invite Trainees Modal */}
      {showInviteModal && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-dialog">
            <div className="admin-modal-header">
              <h3 className="admin-modal-title">Invite Trainee to {currentBatch.name}</h3>
              <button 
                type="button" 
                className="admin-modal-close-btn"
                onClick={() => setShowInviteModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSendInvite}>
              <div className="admin-modal-form-group">
                <label className="admin-modal-label">Role</label>
                <select className="admin-modal-select" value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}><option value="TRAINEE">Trainee</option><option value="TA">Teaching Assistant (TA)</option></select>
              </div>
              <div className="admin-modal-form-group">
                <label className="admin-modal-label">Trainee Corporate Email</label>
                <input 
                  type="email"
                  className="admin-modal-input"
                  placeholder="trainee.name@institution.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  required
                />
              </div>

              <p style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                The trainee will receive a one-time onboarding link assigned directly to {currentBatch.name}.
              </p>

              <div className="admin-modal-buttons-row">
                <button 
                  type="button" 
                  className="admin-btn-outline"
                  onClick={() => setShowInviteModal(false)}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="admin-btn-dark"
                >
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
