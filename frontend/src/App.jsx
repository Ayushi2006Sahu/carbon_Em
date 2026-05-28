import React, { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || '';

export default function App() {
  // Global Data States
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [auditTrail, setAuditTrail] = useState([]);
  const [rejectionTarget, setRejectionTarget] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Filtering States
  const [filterScope, setFilterScope] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSuspicious, setFilterSuspicious] = useState('');

  // Ingestion File States
  const [sapFile, setSapFile] = useState(null);
  const [sapStatus, setSapStatus] = useState({ state: 'idle', msg: '' });
  
  const [utilityFile, setUtilityFile] = useState(null);
  const [utilityStatus, setUtilityStatus] = useState({ state: 'idle', msg: '' });
  
  const [travelFile, setTravelFile] = useState(null);
  const [travelStatus, setTravelStatus] = useState({ state: 'idle', msg: '' });

  // Load dashboard aggregates & records
  const fetchDashboardData = async () => {
    try {
      const summaryRes = await fetch(`${API_BASE}/api/dashboard/summary/`);
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }
    } catch (err) {
      console.error("Error loading dashboard summary:", err);
    }
  };

  const fetchRecords = async () => {
    try {
      const params = new URLSearchParams();
      if (filterScope) params.append('scope', filterScope);
      if (filterCategory) params.append('category', filterCategory);
      if (filterStatus) params.append('status', filterStatus);
      if (filterSuspicious) params.append('is_suspicious', filterSuspicious);

      const recordsRes = await fetch(`${API_BASE}/api/records/?${params.toString()}`);
      if (recordsRes.ok) {
        const data = await recordsRes.json();
        setRecords(data);
      }
    } catch (err) {
      console.error("Error loading records list:", err);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    fetchRecords();
  }, [filterScope, filterCategory, filterStatus, filterSuspicious]);

  // Upload handler
  const handleUpload = async (e, sourceType, file, setFile, setStatus) => {
    e.preventDefault();
    if (!file) {
      setStatus({ state: 'error', msg: 'Please select a CSV file first.' });
      return;
    }

    setStatus({ state: 'uploading', msg: 'Processing file on ESG Engine...' });
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/ingest/${sourceType.toLowerCase()}/`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setStatus({ state: 'success', msg: `${sourceType} file successfully parsed! ${data.records_created} records created.` });
        setFile(null);
        // Clear file input manually
        e.target.reset();
        
        // Refresh dashboard
        fetchDashboardData();
        fetchRecords();
      } else {
        setStatus({ state: 'error', msg: data.error || 'Ingestion failed.' });
      }
    } catch (err) {
      setStatus({ state: 'error', msg: 'Connection to backend failed.' });
    }
  };

  // Action: Approve
  const handleApprove = async (recordId) => {
    if (!window.confirm("Are you sure you want to approve this carbon emission record? This action will write to compliance logs.")) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/records/${recordId}/approve/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        fetchDashboardData();
        fetchRecords();
        if (selectedRecord && selectedRecord.id === recordId) {
          openRecordDetails(recordId); // refresh modal audit trail
        }
      } else {
        const data = await res.json();
        alert(data.error || "Approval failed.");
      }
    } catch (err) {
      alert("Failed to communicate with API.");
    }
  };

  // Action: Reject
  const handleRejectSubmit = async (e) => {
    e.preventDefault();
    if (!rejectionReason.trim()) {
      alert("Please provide a rejection reason.");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/records/${rejectionTarget}/reject/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: rejectionReason })
      });
      if (res.ok) {
        setRejectionTarget(null);
        setRejectionReason('');
        fetchDashboardData();
        fetchRecords();
        if (selectedRecord && selectedRecord.id === rejectionTarget) {
          setSelectedRecord(null); // Close modal if open
        }
      } else {
        const data = await res.json();
        alert(data.error || "Rejection failed.");
      }
    } catch (err) {
      alert("Failed to communicate with API.");
    }
  };

  // Open modal audit details
  const openRecordDetails = async (record) => {
    setSelectedRecord(record);
    try {
      const auditRes = await fetch(`${API_BASE}/api/records/${record.id}/audit/`);
      if (auditRes.ok) {
        const data = await auditRes.json();
        setAuditTrail(data);
      }
    } catch (err) {
      console.error("Error loading audit log:", err);
    }
  };

  // Convert KG to Tonnes for display
  const toTonnes = (kg) => {
    if (!kg) return '0.000';
    return (parseFloat(kg) / 1000.0).toFixed(3);
  };

  return (
    <div className="app-container">
      {/* Header Dashboard */}
      <header className="dashboard-header">
        <div className="brand-section">
          <div className="brand-logo-glow">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0b0f19" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 3.5 0 9.5C17 17 15 20 11 20z"></path>
              <path d="M19 2c-2.26 4.33-5.27 7.14-8 8"></path>
            </svg>
          </div>
          <div>
            <h1 className="brand-title">Breathe ESG</h1>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Enterprise Emissions Ingestion & Analyst Audit Platform</p>
          </div>
        </div>
        <div className="header-meta">
          <div className="meta-badge">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            Tenant: <span>{summary ? summary.tenant_name : 'Loading...'}</span>
          </div>
          <div className="meta-badge">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Analyst: <span>analyst_jane</span>
          </div>
        </div>
      </header>

      {/* KPI Cards Grid */}
      <section className="kpi-grid">
        <div className="glass-card kpi-card">
          <span className="kpi-label">Total Ingested Records</span>
          <span className="kpi-value">{summary ? summary.total_records : '0'}</span>
          <span className="kpi-unit">rows uploaded</span>
        </div>
        <div className="glass-card kpi-card kpi-pending">
          <span className="kpi-label">Pending Review</span>
          <span className="kpi-value text-amber">{summary ? summary.pending_count : '0'}</span>
          <span className="kpi-unit">require attention</span>
        </div>
        <div className="glass-card kpi-card kpi-suspicious">
          <span className="kpi-label">Flagged Anomalies</span>
          <span className="kpi-value text-crimson">{summary ? summary.suspicious_count : '0'}</span>
          <span className="kpi-unit">triggered suspicion checks</span>
        </div>
        <div className="glass-card kpi-card kpi-approved">
          <span className="kpi-label">Verified Approved</span>
          <span className="kpi-value text-emerald">{summary ? summary.approved_count : '0'}</span>
          <span className="kpi-unit">ready for audit</span>
        </div>
        <div className="glass-card kpi-card kpi-total-footprint">
          <span className="kpi-label">Approved Carbon Footprint</span>
          <span className="kpi-value text-emerald">{summary ? toTonnes(summary.approved_footprint_kg) : '0.00'}</span>
          <span className="kpi-unit">Metric Tonnes CO2e</span>
          <div className="scope-distribution">
            <div className="scope-indicator">
              Scope 1
              <strong>{summary ? toTonnes(summary.scope_breakdown_kg.scope1) : '0.00'} t</strong>
            </div>
            <div className="scope-indicator">
              Scope 2
              <strong>{summary ? toTonnes(summary.scope_breakdown_kg.scope2) : '0.00'} t</strong>
            </div>
            <div className="scope-indicator">
              Scope 3
              <strong>{summary ? toTonnes(summary.scope_breakdown_kg.scope3) : '0.00'} t</strong>
            </div>
          </div>
        </div>
      </section>

      {/* Main Workspace split */}
      <div className="content-grid">
        {/* Left Side: Upload Panel */}
        <aside className="upload-panel">
          {/* SAP File Ingestion */}
          <div className="glass-card highlight-emerald">
            <h3 className="upload-card-title">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-emerald)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              SAP Ingestion
            </h3>
            <form className="upload-form" onSubmit={(e) => handleUpload(e, 'SAP', sapFile, setSapFile, setSapStatus)}>
              <div className="source-upload-container">
                <div className="upload-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                </div>
                <span className="upload-label">Upload SAP Fuel & Procurements</span>
                <span className="upload-hint">Drag CSV here or click to browse</span>
                <input type="file" accept=".csv" onChange={(e) => {
                  setSapFile(e.target.files[0]);
                  setSapStatus({ state: 'idle', msg: '' });
                }} />
              </div>
              {sapFile && (
                <div className="selected-file-pill">
                  📎 {sapFile.name} ({(sapFile.size / 1024).toFixed(1)} KB)
                </div>
              )}
              {sapStatus.msg && (
                <div style={{
                  fontSize: '0.8rem',
                  padding: '0.5rem',
                  borderRadius: '6px',
                  backgroundColor: sapStatus.state === 'error' ? 'rgba(239,68,68,0.1)' : sapStatus.state === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.03)',
                  color: sapStatus.state === 'error' ? '#fca5a5' : sapStatus.state === 'success' ? '#a7f3d0' : 'var(--text-secondary)',
                  border: `1px solid ${sapStatus.state === 'error' ? 'rgba(239,68,68,0.2)' : sapStatus.state === 'success' ? 'rgba(16,185,129,0.2)' : 'var(--border-glass)'}`
                }}>
                  {sapStatus.msg}
                </div>
              )}
              <button type="submit" className="btn-upload" disabled={!sapFile || sapStatus.state === 'uploading'}>
                {sapStatus.state === 'uploading' ? 'Parsing...' : 'Analyze CSV'}
              </button>
            </form>
          </div>

          {/* Utility Ingestion */}
          <div className="glass-card highlight-emerald">
            <h3 className="upload-card-title">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-emerald)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
              Utility Ingestion
            </h3>
            <form className="upload-form" onSubmit={(e) => handleUpload(e, 'UTILITY', utilityFile, setUtilityFile, setUtilityStatus)}>
              <div className="source-upload-container">
                <div className="upload-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                </div>
                <span className="upload-label">Upload Electricity Utility Data</span>
                <span className="upload-hint">Drag CSV here or click to browse</span>
                <input type="file" accept=".csv" onChange={(e) => {
                  setUtilityFile(e.target.files[0]);
                  setUtilityStatus({ state: 'idle', msg: '' });
                }} />
              </div>
              {utilityFile && (
                <div className="selected-file-pill">
                  📎 {utilityFile.name} ({(utilityFile.size / 1024).toFixed(1)} KB)
                </div>
              )}
              {utilityStatus.msg && (
                <div style={{
                  fontSize: '0.8rem',
                  padding: '0.5rem',
                  borderRadius: '6px',
                  backgroundColor: utilityStatus.state === 'error' ? 'rgba(239,68,68,0.1)' : utilityStatus.state === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.03)',
                  color: utilityStatus.state === 'error' ? '#fca5a5' : utilityStatus.state === 'success' ? '#a7f3d0' : 'var(--text-secondary)',
                  border: `1px solid ${utilityStatus.state === 'error' ? 'rgba(239,68,68,0.2)' : utilityStatus.state === 'success' ? 'rgba(16,185,129,0.2)' : 'var(--border-glass)'}`
                }}>
                  {utilityStatus.msg}
                </div>
              )}
              <button type="submit" className="btn-upload" disabled={!utilityFile || utilityStatus.state === 'uploading'}>
                {utilityStatus.state === 'uploading' ? 'Parsing...' : 'Analyze CSV'}
              </button>
            </form>
          </div>

          {/* Travel Ingestion */}
          <div className="glass-card highlight-emerald">
            <h3 className="upload-card-title">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-emerald)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 2-3-.5c-.3-.1-.7.1-.9.4l-.2.4c-.2.5-.1 1 .3 1.2l3.5 2 2 3.5c.2.4.7.5 1.2.3l.4-.2c.3-.2.5-.6.4-.9l-.5-3 2-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.3c.4-.2.6-.6.5-1.1z"></path>
              </svg>
              Corporate Travel Ingestion
            </h3>
            <form className="upload-form" onSubmit={(e) => handleUpload(e, 'TRAVEL', travelFile, setTravelFile, setTravelStatus)}>
              <div className="source-upload-container">
                <div className="upload-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                </div>
                <span className="upload-label">Upload Concur Expenses Log</span>
                <span className="upload-hint">Drag CSV here or click to browse</span>
                <input type="file" accept=".csv" onChange={(e) => {
                  setTravelFile(e.target.files[0]);
                  setTravelStatus({ state: 'idle', msg: '' });
                }} />
              </div>
              {travelFile && (
                <div className="selected-file-pill">
                  📎 {travelFile.name} ({(travelFile.size / 1024).toFixed(1)} KB)
                </div>
              )}
              {travelStatus.msg && (
                <div style={{
                  fontSize: '0.8rem',
                  padding: '0.5rem',
                  borderRadius: '6px',
                  backgroundColor: travelStatus.state === 'error' ? 'rgba(239,68,68,0.1)' : travelStatus.state === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.03)',
                  color: travelStatus.state === 'error' ? '#fca5a5' : travelStatus.state === 'success' ? '#a7f3d0' : 'var(--text-secondary)',
                  border: `1px solid ${travelStatus.state === 'error' ? 'rgba(239,68,68,0.2)' : travelStatus.state === 'success' ? 'rgba(16,185,129,0.2)' : 'var(--border-glass)'}`
                }}>
                  {travelStatus.msg}
                </div>
              )}
              <button type="submit" className="btn-upload" disabled={!travelFile || travelStatus.state === 'uploading'}>
                {travelStatus.state === 'uploading' ? 'Parsing...' : 'Analyze CSV'}
              </button>
            </form>
          </div>
        </aside>

        {/* Right Side: Ledger Table */}
        <main className="ledger-panel glass-card">
          <div className="ledger-header">
            <div className="ledger-title-group">
              <h2 style={{ fontSize: '1.4rem', fontWeight: '700' }}>Emissions Ledger</h2>
              <span className="ledger-subtitle">Showing {records.length} resolved records</span>
            </div>

            {/* Filter controls */}
            <div className="filters-bar">
              <select className="filter-select" value={filterScope} onChange={(e) => setFilterScope(e.target.value)}>
                <option value="">All Scopes</option>
                <option value="1">Scope 1</option>
                <option value="2">Scope 2</option>
                <option value="3">Scope 3</option>
              </select>
              <select className="filter-select" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
                <option value="">All Categories</option>
                <option value="fuel">Fuel Combustion</option>
                <option value="electricity">Grid Electricity</option>
                <option value="flight">Air Travel</option>
                <option value="hotel">Hotel Stays</option>
                <option value="ground">Ground Transport</option>
              </select>
              <select className="filter-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                <option value="">All Statuses</option>
                <option value="pending_review">Pending Review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <select className="filter-select" value={filterSuspicious} onChange={(e) => setFilterSuspicious(e.target.value)}>
                <option value="">Anomaly Filter</option>
                <option value="true">Suspicious Only</option>
                <option value="false">Clear Records</option>
              </select>
            </div>
          </div>

          {/* Records Table */}
          <div className="table-container">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Scope</th>
                  <th>Category</th>
                  <th>Quantity / Activity</th>
                  <th>Footprint (tCO2e)</th>
                  <th>Dates</th>
                  <th>State</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      No emission records found. Seed CSVs using the left panel upload forms to begin analyst audits.
                    </td>
                  </tr>
                ) : (
                  records.map((rec) => (
                    <tr key={rec.id} className={rec.is_suspicious ? 'row-suspicious' : ''}>
                      <td>
                        <span className="badge-scope">Scope {rec.scope}</span>
                      </td>
                      <td style={{ textTransform: 'capitalize' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '1.1rem' }}>
                            {rec.category === 'flight' ? '✈️' : rec.category === 'electricity' ? '⚡' : rec.category === 'hotel' ? '🏨' : rec.category === 'ground' ? '🚗' : '⛽'}
                          </span>
                          <div>
                            <strong>{rec.category}</strong>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{rec.source_type} Ingestion</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <strong>{parseFloat(rec.activity_value).toLocaleString()}</strong> <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{rec.activity_unit}</span>
                      </td>
                      <td>
                        <strong style={{ fontSize: '1rem' }} className="text-emerald">{toTonnes(rec.normalized_value_kg_co2e)} t</strong>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>EF: {rec.emission_factor_used}</div>
                      </td>
                      <td>
                        <div style={{ fontSize: '0.85rem' }}>{rec.period_start}</div>
                        {rec.period_start !== rec.period_end && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>to {rec.period_end}</div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', alignItems: 'flex-start' }}>
                          <span className={`badge-status status-${rec.status.replace('_', '')}`}>
                            {rec.status.replace('_', ' ')}
                          </span>
                          {rec.is_suspicious && (
                            <span className="badge-suspicious" title={rec.suspicion_reason}>
                              ⚠️ ANOMALY
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="btn-action-group" style={{ justifyContent: 'flex-end' }}>
                          <button className="btn-icon" title="View Audit Trail & Detail" onClick={() => openRecordDetails(rec)}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                          </button>
                          
                          {rec.status !== 'approved' ? (
                            <>
                              <button className="btn-icon btn-approve" title="Approve compliance record" onClick={() => handleApprove(rec.id)}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                              </button>
                              <button className="btn-icon btn-reject" title="Reject record for correction" onClick={() => {
                                setRejectionTarget(rec.id);
                                setRejectionReason('');
                              }}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                              </button>
                            </>
                          ) : (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', paddingRight: '0.5rem' }}>Auditable</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Inline Rejection Prompt */}
          {rejectionTarget && (
            <div className="rejection-dialog" style={{ animation: 'fadeIn 0.2s' }}>
              <h4 className="rejection-dialog-title">🚨 Reject compliance record {rejectionTarget}</h4>
              <form onSubmit={handleRejectSubmit}>
                <textarea
                  className="rejection-textarea"
                  placeholder="Explain why this data is rejected (e.g. Unit mismatch, excessive outlier value, billing span error)..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  required
                />
                <div className="btn-dialog-group">
                  <button type="button" className="btn-dialog-cancel" onClick={() => setRejectionTarget(null)}>Cancel</button>
                  <button type="submit" className="btn-dialog-confirm">Confirm Rejection</button>
                </div>
              </form>
            </div>
          )}
        </main>
      </div>

      {/* MODAL DETAILED WORKSPACE + AUDIT TIMELINE */}
      {selectedRecord && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ animation: 'fadeIn 0.2s' }}>
            <div className="modal-header">
              <h3 className="modal-title">
                Compliance Audit Trail — Record ID #{selectedRecord.id}
              </h3>
              <button className="btn-close" onClick={() => { setSelectedRecord(null); setAuditTrail([]); }}>&times;</button>
            </div>

            <div className="modal-body">
              {/* Status Banner */}
              <div style={{
                background: selectedRecord.status === 'approved' ? 'rgba(16,185,129,0.06)' : selectedRecord.status === 'rejected' ? 'rgba(239,68,68,0.06)' : 'rgba(245,158,11,0.06)',
                border: `1px solid ${selectedRecord.status === 'approved' ? 'rgba(16,185,129,0.15)' : selectedRecord.status === 'rejected' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)'}`,
                padding: '1rem',
                borderRadius: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Auditing Status</span>
                  <div style={{ fontSize: '1.2rem', fontWeight: '700' }} className={selectedRecord.status === 'approved' ? 'text-emerald' : selectedRecord.status === 'rejected' ? 'text-crimson' : 'text-amber'}>
                    {selectedRecord.status.replace('_', ' ').toUpperCase()}
                  </div>
                </div>
                {selectedRecord.status !== 'approved' && (
                  <div className="btn-action-group">
                    <button className="btn-upload" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }} onClick={() => handleApprove(selectedRecord.id)}>
                      Approve compliance record
                    </button>
                    <button className="btn-dialog-confirm" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }} onClick={() => {
                      setRejectionTarget(selectedRecord.id);
                      setRejectionReason('');
                    }}>
                      Reject
                    </button>
                  </div>
                )}
              </div>

              {/* Record Attributes Grid */}
              <div className="detail-grid">
                <div className="detail-item">
                  <label>Scope & Category</label>
                  <span>Scope {selectedRecord.scope} — {selectedRecord.category}</span>
                </div>
                <div className="detail-item">
                  <label>Ingested Quantity</label>
                  <span>{parseFloat(selectedRecord.activity_value).toLocaleString()} {selectedRecord.activity_unit}</span>
                </div>
                <div className="detail-item">
                  <label>Normalized Carbon Value</label>
                  <span className="text-emerald">{toTonnes(selectedRecord.normalized_value_kg_co2e)} tCO2e</span>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>({parseFloat(selectedRecord.normalized_value_kg_co2e).toLocaleString()} kg)</div>
                </div>
                <div className="detail-item">
                  <label>Emission Factor Applied</label>
                  <span>{selectedRecord.emission_factor_used}</span>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>kgCO2e per activity unit</div>
                </div>
                <div className="detail-item">
                  <label>Reporting Dates</label>
                  <span>{selectedRecord.period_start} to {selectedRecord.period_end}</span>
                </div>
                <div className="detail-item">
                  <label>Original Invoice Ref</label>
                  <span style={{ fontSize: '0.9rem', fontFamily: 'monospace' }}>{selectedRecord.source_ref}</span>
                </div>
              </div>

              {/* Suspicious Alerts */}
              {selectedRecord.is_suspicious && (
                <div style={{
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  padding: '1.25rem',
                  borderRadius: '10px',
                  display: 'flex',
                  gap: '0.75rem'
                }}>
                  <div style={{ fontSize: '1.5rem' }}>⚠️</div>
                  <div>
                    <strong style={{ color: '#fca5a5', display: 'block', marginBottom: '0.25rem' }}>Anomalous Suspicion Detected</strong>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{selectedRecord.suspicion_reason}</p>
                  </div>
                </div>
              )}

              {/* Vertical Audit Timeline */}
              <div className="timeline-section">
                <h4 className="timeline-title">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                  Compliance Audit Log Ledger
                </h4>
                <div className="timeline-container">
                  {auditTrail.map((log) => (
                    <div key={log.id} className={`timeline-node node-${log.action}`}>
                      <div className="node-meta">
                        <span className="node-title text-emerald">
                          {log.action.toUpperCase()}
                        </span>
                        <span>{new Date(log.changed_at).toLocaleString()}</span>
                      </div>
                      <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                        Executed by: <strong>{log.changed_by_username || 'System'}</strong> ({log.changed_by_role || 'Automation Engine'})
                      </div>
                      
                      {log.action === 'ingested' && (
                        <div className="node-content">
                          Initial compliance values ingested and locked. Standard emission factors computed.
                        </div>
                      )}
                      {log.action === 'approved' && (
                        <div className="node-content" style={{ borderLeft: '3px solid var(--color-emerald)' }}>
                          Auditable carbon values reviewed and authorized. Status transitioned to <strong>APPROVED</strong>.
                        </div>
                      )}
                      {log.action === 'rejected' && (
                        <div className="node-content" style={{ borderLeft: '3px solid var(--color-crimson)', background: 'rgba(239, 68, 68, 0.02)' }}>
                          Status changed to <strong>REJECTED</strong>. Compliance reason recorded:
                          <div style={{ color: '#fca5a5', fontStyle: 'italic', marginTop: '0.25rem' }}>
                            &ldquo;{log.after_state?.suspicion_reason?.split('Rejected by Analyst: ')[1] || 'No reason specified'}&rdquo;
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
