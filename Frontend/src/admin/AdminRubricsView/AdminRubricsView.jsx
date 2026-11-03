import React, { useEffect, useState } from 'react';
import './AdminRubricsView.css';
import { useApp } from '../../context/AppContext.jsx';

export function AdminRubricsView({ onNavigateTab }) {
  const { rubrics, api, setAppError, refreshWorkspace } = useApp();
  const activeRubric = rubrics[0] || null;
  // Main Rubric State
  const [rubricTitle, setRubricTitle] = useState('New competency rubric');
  const [currentVersion, setCurrentVersion] = useState('Current');
  const [versionStatus, setVersionStatus] = useState('DRAFT');
  const [criteria, setCriteria] = useState([]);
  const [versions, setVersions] = useState([]);
  const [thresholds] = useState([{id:'L1',level:'L1',range:'0–24%'},{id:'L2',level:'L2',range:'25–49%'},{id:'L3',level:'L3',range:'50–74%'},{id:'L4',level:'L4',range:'75–100%'}]);

  // Status feedback toast
  const [notice, setNotice] = useState(null);

  // Thresholds edit modal
  const [isEditingThresholds, setIsEditingThresholds] = useState(false);
  const [tempThresholds, setTempThresholds] = useState(thresholds);
  useEffect(() => {
    if (!activeRubric) { setCriteria([]); setVersions([]); return; }
    setRubricTitle(activeRubric.name); setVersionStatus(activeRubric.status); setCurrentVersion(`v${activeRubric.version || 1}`);
    setCriteria((activeRubric.criteria || []).map((c) => ({ ...c, lookFor: c.description, levels: c.levels || [] })));
    setVersions([{ version: `v${activeRubric.version || 1}`, status: activeRubric.status === 'ACTIVE' ? 'Live' : 'Draft', statusType: activeRubric.status === 'ACTIVE' ? 'live' : 'draft', subtext: 'Current backend rubric' }]);
  }, [activeRubric?.id, activeRubric?.updated_at]);

  // Calculate total weight
  // Weights in design are 3, 2, 2, 3 (= 10, corresponding to 100%) or entered directly in %
  const rawSum = criteria.reduce((sum, c) => sum + (Number(c.weight) || 0), 0);
  const totalWeightPercent = rawSum <= 10 ? Math.round(rawSum * 10) : Math.round(rawSum);
  const isWeightValid = totalWeightPercent === 100;

  // Update a single criterion field
  const handleUpdateCriterion = (id, field, value) => {
    setCriteria(prev =>
      prev.map(item => {
        if (item.id === id) {
          return { ...item, [field]: value };
        }
        return item;
      })
    );
  };

  // Delete a criterion
  const handleDeleteCriterion = (id) => {
    if (criteria.length <= 1) {
      alert('A rubric must have at least one criterion.');
      return;
    }
    setCriteria(prev => prev.filter(item => item.id !== id));
  };

  // Add new criterion
  const handleAddCriterion = () => {
    const nextIndex = criteria.length + 1;
    const newCrit = {
      id: `crit-${Date.now()}`,
      name: `Criterion ${nextIndex}`,
      weight: 0,
      lookFor: '',
      max_score: 100,
      levels: ['L1','L2','L3','L4'].map((level) => ({ level, description: `${level} competency description` }))
    };
    setCriteria([...criteria, newCrit]);
  };

  // Save draft
  const handleSaveDraft = async () => {
    const payload = { name: rubricTitle, description: activeRubric?.description || '', criteria: criteria.map(({ id, lookFor, levels, ...c }) => ({ ...(Number.isInteger(id) ? { id } : {}), name: c.name, description: lookFor || c.description || '', weight: Number(c.weight), max_score: Number(c.max_score || 100), levels: levels?.length === 4 ? levels : ['L1','L2','L3','L4'].map((level) => ({level, description:`${level} competency description`})) })) };
    try { if (activeRubric) await api.request(`/rubrics/${activeRubric.id}/`, {method:'PATCH',body:JSON.stringify(payload)}); else await api.request('/rubrics/', {method:'POST',body:JSON.stringify(payload)}); await refreshWorkspace(); setNotice({type:'draft',message:`Rubric "${rubricTitle}" saved to the backend.`}); }
    catch (error) { setAppError(error.message); }
  };

  // Publish v3
  const handlePublishV3 = async () => {
    if (!isWeightValid) {
      alert(`Cannot publish: Total weight is ${totalWeightPercent}%. It must equal 100% to publish.`);
      return;
    }

    try { let rubricId = activeRubric?.id; if (!rubricId) { await handleSaveDraft(); await refreshWorkspace(); rubricId = (await api.all('/rubrics/')).find((r) => r.name === rubricTitle)?.id; } if (!rubricId) throw new Error('Save the rubric first.'); await api.request(`/rubrics/${rubricId}/activate/`, {method:'POST'}); await refreshWorkspace(); setVersionStatus('ACTIVE'); setNotice({type:'success',message:`Rubric "${rubricTitle}" is active.`}); } catch (error) { setAppError(error.message); }
  };

  // Save thresholds modal
  const handleSaveThresholds = () => {
    setIsEditingThresholds(false);
    setNotice({
      type: 'draft',
      message: 'Threshold cutoffs are currently fixed by the backend scoring rule (equal score bands).'
    });
    setTimeout(() => setNotice(null), 3000);
  };

  return (
    <div className="admin-rubrics-container">
      {/* Breadcrumb Navigation */}
      <div className="admin-rubrics-breadcrumb">
        <span 
          className="admin-rubrics-breadcrumb-link"
          onClick={() => onNavigateTab && onNavigateTab('overview')}
        >
          Rubrics
        </span>
        <span className="admin-rubrics-breadcrumb-separator">&gt;</span>
        <span className="admin-rubrics-breadcrumb-current">{rubricTitle}</span>
      </div>

      {/* Header Row */}
      <div className="admin-rubrics-header-row">
        <div className="admin-rubrics-header-left">
          <div className="admin-rubrics-title-row">
            <h1 className="admin-rubrics-title">{rubricTitle}</h1>
            <span className={`admin-rubrics-version-pill ${versionStatus === 'v3 live' ? 'live' : ''}`}>
              {versionStatus}
            </span>
          </div>
          <p className="admin-rubrics-subtitle">
            Editing creates v3. Scores already given on v2 stay exactly as they are.
          </p>
        </div>

        <div className="admin-rubrics-header-actions">
          <button
            type="button"
            className="admin-btn-rubric-draft"
            onClick={handleSaveDraft}
          >
            Save draft
          </button>
          <button
            type="button"
            className="admin-btn-rubric-publish"
            onClick={handlePublishV3}
          >
            Publish v3
          </button>
        </div>
      </div>

      {/* Feedback Toast Notice */}
      {notice && (
        <div style={{
          backgroundColor: notice.type === 'success' ? '#ecfdf5' : '#eff6ff',
          border: `1.5px solid ${notice.type === 'success' ? '#10b981' : '#3b82f6'}`,
          borderRadius: '8px',
          padding: '12px 18px',
          marginBottom: '20px',
          color: notice.type === 'success' ? '#065f46' : '#1e40af',
          fontSize: '13.5px',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span>{notice.type === 'success' ? '✓ ' : 'ℹ '}{notice.message}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main 2-Column Grid */}
      <div className="admin-rubrics-grid">
        {/* Left Column: Weight Banner & Criteria Cards */}
        <div className="admin-rubrics-main-col">
          {/* Total Weight Status Banner */}
          <div className="admin-rubrics-weight-banner">
            <div className="admin-weight-banner-left">
              {isWeightValid ? (
                <div className="admin-weight-check-circle">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              ) : (
                <div className="admin-weight-warning-circle">!</div>
              )}
              <div>
                <span className="admin-weight-banner-text">
                  Total weight {totalWeightPercent}%
                </span>
                <span className="admin-weight-banner-status">
                  {isWeightValid ? 'Ready to publish' : 'Weights must sum to 100%'}
                </span>
              </div>
            </div>
          </div>

          {/* Criteria Cards */}
          {criteria.map((crit, index) => (
            <div key={crit.id} className="admin-criterion-card">
              <div className="admin-criterion-header">
                Criterion {index + 1}
              </div>

              {/* Name & Weight Row */}
              <div className="admin-criterion-row-top">
                <div className="admin-criterion-name-group">
                  <input
                    type="text"
                    className="admin-criterion-input"
                    value={crit.name}
                    onChange={(e) => handleUpdateCriterion(crit.id, 'name', e.target.value)}
                    placeholder="Criterion title (e.g. API design)"
                  />
                </div>

                <div className="admin-criterion-weight-group">
                  <span className="admin-criterion-weight-label">Weight</span>
                  <div className="admin-criterion-weight-controls">
                    <input
                      type="number"
                      className="admin-weight-input-box"
                      value={crit.weight}
                      onChange={(e) => handleUpdateCriterion(crit.id, 'weight', e.target.value)}
                      min="1"
                      max="100"
                    />
                    <div className="admin-weight-unit-badge">%</div>
                    <button
                      type="button"
                      className="admin-criterion-delete-btn"
                      onClick={() => handleDeleteCriterion(crit.id)}
                      title="Delete criterion"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>

              {/* What the AI should look for */}
              <div className="admin-criterion-lookfor-group">
                <label className="admin-criterion-lookfor-label">
                  What the AI should look for
                </label>
                <input
                  type="text"
                  className="admin-criterion-lookfor-input"
                  value={crit.lookFor}
                  onChange={(e) => handleUpdateCriterion(crit.id, 'lookFor', e.target.value)}
                  placeholder="Key criteria, validations, edge cases the AI assessor checks..."
                />
              </div>
            </div>
          ))}

          {/* Add Criterion Button */}
          <button
            type="button"
            className="admin-btn-add-criterion"
            onClick={handleAddCriterion}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add criterion
          </button>
        </div>

        {/* Right Column: Sidebar Cards */}
        <aside className="admin-rubrics-sidebar">
          {/* Card 1: Version History */}
          <div className="admin-rubrics-sidebar-card">
            <h3 className="admin-sidebar-card-title">Version history</h3>
            <div className="admin-version-history-list">
              {versions.map((ver) => (
                <div key={ver.version} className="admin-version-history-item">
                  <div className="admin-version-item-left">
                    <span className="admin-version-label">{ver.version}</span>
                    <span className="admin-version-subtext">{ver.subtext}</span>
                  </div>
                  <span className={`admin-version-pill ${ver.statusType}`}>
                    {ver.statusType === 'live' && (
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    {ver.statusType === 'archived' && (
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    )}
                    {ver.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Card 2: Level Thresholds */}
          <div className="admin-rubrics-sidebar-card">
            <h3 className="admin-sidebar-card-title">Level thresholds</h3>
            <div className="admin-thresholds-list">
              {thresholds.map((th) => (
                <div key={th.id} className="admin-threshold-row">
                  <span className="admin-threshold-level">{th.level}</span>
                  <span className="admin-threshold-range">{th.range}</span>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="admin-edit-thresholds-link"
              disabled
              title="Thresholds are fixed by the backend scoring rule."
            >
              Edit thresholds
            </button>
          </div>

          {/* Card 3: Information Callout */}
          <div className="admin-rubrics-info-callout">
            <div className="admin-callout-icon">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
            </div>
            <div className="admin-callout-content">
              <span className="admin-callout-title">
                Trainees can see criteria names
              </span>
              <span className="admin-callout-desc">
                They see names and weights on their report, not the "look for" text.
              </span>
            </div>
          </div>
        </aside>
      </div>

      {/* Thresholds Modal */}
      {isEditingThresholds && (
        <div className="modal-overlay" style={{ zIndex: 1000 }}>
          <div className="modal-dialog" style={{ maxWidth: '480px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 className="modal-dialog-title" style={{ margin: 0 }}>
                Edit Level Thresholds
              </h3>
              <button
                type="button"
                className="btn-remove-file"
                onClick={() => setIsEditingThresholds(false)}
              >
                ✕
              </button>
            </div>

            <p className="modal-dialog-desc" style={{ marginBottom: '16px' }}>
              Define the proficiency boundaries for assessment scores:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
              {tempThresholds.map((t, idx) => (
                <div key={t.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a', minWidth: '140px' }}>
                    {t.level}
                  </span>
                  <input
                    type="text"
                    className="admin-form-input"
                    value={t.range}
                    onChange={(e) => {
                      const updated = [...tempThresholds];
                      updated[idx] = { ...updated[idx], range: e.target.value };
                      setTempThresholds(updated);
                    }}
                    style={{ fontSize: '13px', padding: '6px 10px' }}
                  />
                </div>
              ))}
            </div>

            <div className="modal-buttons-row" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="admin-btn-save-draft"
                onClick={() => setIsEditingThresholds(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="admin-btn-assign-primary"
                onClick={handleSaveThresholds}
              >
                Save thresholds
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
