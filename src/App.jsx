import React, { useEffect, useMemo, useState } from 'react';
import './App.css';
import { getScreeningResults, listScreeningCases, startScreening, uploadDocument } from './api/client';

const defaultForm = {
  documentType: '',
  documentFile: null,
  personFile: null,
};

const normalizeCaseResult = (screeningCase) => {
  if (!screeningCase) return null;

  const ocr = screeningCase.ocrResultId || screeningCase.ocr || {};
  const validation = screeningCase.validationResultId || screeningCase.validation || {};
  const tampering = screeningCase.tamperingResultId || screeningCase.tampering || {};
  const face = screeningCase.faceVerificationResultId || screeningCase.face || {};
  const risk = screeningCase.riskAssessmentId || screeningCase.risk || {};
  const validationDetails = validation.validationDetails || {};
  const violations = Array.isArray(validationDetails.violations) ? validationDetails.violations : (validation.violations || []);

  return {
    documentType: screeningCase.documentId?.documentType || ocr.documentType || 'unknown',
    ocr: {
      fields: ocr.fields || {},
      confidence: ocr.confidence ?? 0,
      status: ocr.status || 'unknown',
      missingFields: ocr.missingFields || [],
      warnings: ocr.warnings || [],
    },
    validation: {
      isValid: validation.isValid ?? validation.status === 'valid',
      errors: violations.filter((item) => item.severity === 'error'),
      warnings: violations.filter((item) => item.severity === 'warning'),
    },
    tampering: {
      tamperingDetected: !!tampering.tamperingDetected,
      confidence: tampering.confidence ?? 0,
      assessment: tampering.assessment || (tampering.tamperingDetected ? 'review' : 'inconclusive'),
      findings: tampering.findings || [],
    },
    face: {
      faceDetectedInDocument: !!face.faceDetectedInDocument,
      faceDetectedInPerson: !!face.faceDetectedInPerson,
      matchStatus: face.matchStatus || 'not_verified',
      similarity: face.similarity ?? 0,
      confidence: face.confidence ?? 0,
    },
    risk: {
      riskScore: risk.riskScore ?? 0,
      riskLevel: risk.riskLevel || 'LOW',
      requiresHumanReview: !!risk.requiresHumanReview,
      factors: risk.factors || [],
      recommendation: risk.recommendation || 'Manual review recommended.',
    },
    requiresHumanReview: !!screeningCase.requiresHumanReview || !!risk.requiresHumanReview,
    status: screeningCase.status || (screeningCase.success ? 'completed' : 'pending'),
  };
};

const formatFieldLabel = (fieldName) => {
  return String(fieldName || '')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const getValidationState = (validation) => {
  const errors = validation?.errors || [];
  const warnings = validation?.warnings || [];

  if (errors.length) {
    return { label: 'Failed', className: 'invalid' };
  }

  if (warnings.length) {
    return { label: 'Warning', className: 'warning' };
  }

  return { label: 'Valid', className: 'valid' };
};

function App() {
  const [form, setForm] = useState(defaultForm);
  const [uploadedDocumentId, setUploadedDocumentId] = useState('');
  const [uploadedPersonId, setUploadedPersonId] = useState('');
  const [cases, setCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [selectedCase, setSelectedCase] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [caseLoading, setCaseLoading] = useState(false);
  const [error, setError] = useState('');
  const [view, setView] = useState('overview');
  const [historyQuery, setHistoryQuery] = useState('');
  const [historyFilter, setHistoryFilter] = useState('all');

  const stats = useMemo(() => {
    const total = cases.length;
    const suspicious = cases.filter((item) => item.requiresHumanReview || item.status === 'error').length;
    const highRisk = cases.filter((item) => ['HIGH', 'CRITICAL'].includes(String(item.riskAssessmentId?.riskLevel || item.riskLevel || '').toUpperCase())).length;
    const pending = cases.filter((item) => item.status === 'processing').length;

    return [
      { label: 'Documents screened', value: total },
      { label: 'Suspicious cases', value: suspicious },
      { label: 'High-risk cases', value: highRisk },
      { label: 'Pending reviews', value: pending },
    ];
  }, [cases]);

  const activeResult = selectedCase ? normalizeCaseResult(selectedCase) : analysisResult;
  const validationState = getValidationState(activeResult?.validation);

  const fetchCases = async () => {
    try {
      const response = await listScreeningCases();
      setCases(response.data || []);
    } catch (err) {
      console.error('Failed to load cases:', err);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  // Keep the activity list current while a backend pipeline is still running.
  useEffect(() => {
    const hasProcessingCase = cases.some((item) => item.status === 'processing');
    if (!hasProcessingCase) return undefined;
    const timer = window.setInterval(fetchCases, 5000);
    return () => window.clearInterval(timer);
  }, [cases]);

  const filteredCases = useMemo(() => cases.filter((item) => {
    const query = historyQuery.trim().toLowerCase();
    const matchesQuery = !query || String(item.caseId || item._id).toLowerCase().includes(query) || String(item.status).toLowerCase().includes(query);
    const risk = String(item.riskAssessmentId?.riskLevel || item.riskLevel || '').toLowerCase();
    const matchesFilter = historyFilter === 'all' || (historyFilter === 'review' ? item.requiresHumanReview : risk === historyFilter);
    return matchesQuery && matchesFilter;
  }), [cases, historyFilter, historyQuery]);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file && (file.size > 10 * 1024 * 1024 || !['image/jpeg', 'image/png', 'application/pdf'].includes(file.type))) {
      setError('Document must be a JPEG, PNG, or PDF file no larger than 10 MB.');
      event.target.value = '';
      return;
    }
    setError('');
    setForm((prev) => ({ ...prev, documentFile: file || null }));
  };

  const handlePersonFileChange = (event) => {
    const file = event.target.files[0];
    if (file && (file.size > 10 * 1024 * 1024 || !file.type.startsWith('image/'))) {
      setError('Person photo must be an image no larger than 10 MB.');
      event.target.value = '';
      return;
    }
    setError('');
    setForm((prev) => ({ ...prev, personFile: file || null }));
  };

  const resetForm = () => {
    setForm(defaultForm);
    setUploadedDocumentId('');
    setUploadedPersonId('');
    setAnalysisResult(null);
    setSelectedCase(null);
    setSelectedCaseId('');
    setError('');
  };

  const exportReport = () => {
    if (!activeResult) { setError('Run or select a screening before exporting a report.'); return; }
    const payload = { exportedAt: new Date().toISOString(), caseId: selectedCase?.caseId || analysisResult?.caseId, result: activeResult };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${payload.caseId || 'screening-report'}.json`; anchor.click(); URL.revokeObjectURL(url);
  };

  const handleSelectCase = async (caseId) => {
    if (!caseId) return;

    setSelectedCaseId(caseId);
    setCaseLoading(true);

    try {
      const response = await getScreeningResults(caseId);
      setSelectedCase(response.data || null);
      setAnalysisResult(null);
    } catch (err) {
      console.error('Failed to load screening case details:', err);
      setError(err.response?.data?.error || 'Unable to load this screening record.');
    } finally {
      setCaseLoading(false);
    }
  };

  const handleAnalyze = async () => {
    try {
      setLoading(true);
      setError('');
      setSelectedCaseId('');
      setSelectedCase(null);

      if (!form.documentFile || !form.documentType) {
        throw new Error('Please select a document and a document type before starting analysis.');
      }

      const documentResponse = await uploadDocument(form.documentFile, form.documentType);
      const documentId = documentResponse.data.documentId || documentResponse.data.document?._id || '';
      setUploadedDocumentId(documentId);

      let personPhotoId = '';
      if (form.personFile) {
        const personResponse = await uploadDocument(form.personFile, 'person_photo');
        personPhotoId = personResponse.data.documentId || personResponse.data.document?._id || '';
        setUploadedPersonId(personPhotoId);
      } else {
        setUploadedPersonId('');
      }

      if (!documentId) {
        throw new Error('Document upload did not return an ID.');
      }

      const response = await startScreening(documentId, personPhotoId || undefined);
      setAnalysisResult(normalizeCaseResult(response.data) || response.data);
      setSelectedCase(null);
      await fetchCases();
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Screening failed.');
    } finally {
      setLoading(false);
    }
  };

  const renderRiskBadge = (level) => {
    return (level || 'LOW').toUpperCase();
  };

  const renderStatusLabel = (value) => {
    const normalized = (value || 'pending').toString().toLowerCase();
    if (normalized === 'processing') return 'Processing';
    if (normalized === 'completed') return 'Completed';
    if (normalized === 'error') return 'Error';
    return 'Pending';
  };

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-dot"><span /></div>
          <div>
            <p className="eyebrow">Security Ops</p>
            <h2>Screening Console</h2>
          </div>
        </div>

        <nav className="nav">
          {[['overview', 'Overview'], ['screening', 'Screening'], ['history', 'History'], ['reviews', 'Reviews']].map(([key, label]) => (
            <button key={key} className={`nav-item ${view === key ? 'active' : ''}`} onClick={() => setView(key)}><span className="nav-marker" />{label}</button>
          ))}
        </nav>
        <div className="sidebar-status"><span className="live-dot" /> All systems operational</div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Dashboard</p>
            <h1>Document screening overview</h1>
          </div>
          <button className="secondary-button" onClick={exportReport}>Export report</button>
        </header>

        {view === 'overview' || view === 'screening' ? <section className="stats-grid">
          {stats.map((stat) => (
            <div className={`stat-card stat-card-${stat.label.split(' ')[0].toLowerCase()}`} key={stat.label}>
              <span className="stat-orb" />
              <p>{stat.label}</p>
              <h3 key={stat.value}>{stat.value}</h3>
              <span className="stat-caption">Live portfolio signal</span>
            </div>
          ))}
        </section> : null}

        {(view === 'overview' || view === 'screening') && <section className="panel-row">
          <div className="panel form-panel">
            <div className="panel-header">
              <h3>New screening</h3>
            </div>

            <div className="form-group">
              <label>Document type</label>
              <select
                value={form.documentType}
                onChange={(e) => setForm((prev) => ({ ...prev, documentType: e.target.value }))}
              >
                <option value="">Select document type</option>
                <option value="passport">Passport</option>
                <option value="visa">Visa</option>
                <option value="national_id">National ID</option>
                <option value="driving_license">Driving license</option>
                <option value="permit">Permit</option>
              </select>
            </div>

            <div className="form-group">
              <label>Document image</label>
              <label className={`file-picker ${form.documentFile ? 'has-file' : ''}`}>
                <input type="file" accept="image/*,.pdf" onChange={handleFileChange} />
                <span className="file-picker-icon">↑</span><span><strong>{form.documentFile ? 'Document attached' : 'Choose a document'}</strong><small>Drop it here or browse your device</small></span>
              </label>
              {form.documentFile ? <span className="file-name">Selected: {form.documentFile.name} ({(form.documentFile.size / 1024 / 1024).toFixed(2)} MB)</span> : <span className="file-hint">JPEG, PNG or PDF · max 10 MB</span>}
            </div>

            <div className="form-group">
              <label>Person image (optional)</label>
              <label className={`file-picker compact ${form.personFile ? 'has-file' : ''}`}>
                <input type="file" accept="image/*" onChange={handlePersonFileChange} />
                <span className="file-picker-icon">+</span><span><strong>{form.personFile ? 'Photo attached' : 'Add a face photo'}</strong><small>Optional · enables face verification</small></span>
              </label>
              {form.personFile ? <span className="file-name">Selected: {form.personFile.name}</span> : <span className="file-hint">Add a clear face photo to enable verification</span>}
            </div>

            {error ? <div className="error-box">{error}</div> : null}

            <div className="button-row"><button className="primary-button" onClick={handleAnalyze} disabled={loading}>
              {loading ? <><span className="button-spinner" />Analyzing document...</> : <>Start analysis <span>→</span></>}
            </button><button className="ghost-button" onClick={resetForm} disabled={loading}>Reset</button></div>

            <div className="upload-summary">
              {uploadedDocumentId ? <p>Document uploaded: {uploadedDocumentId}</p> : null}
              {uploadedPersonId ? <p>Person image uploaded: {uploadedPersonId}</p> : null}
            </div>
          </div>

          <div className="panel latest-panel">
            <div className="panel-header">
              <h3>Recent screening activity</h3>
            </div>

            <div className="activity-list">
              {filteredCases.slice(0, 5).map((item) => (
                <button
                  type="button"
                  className={`activity-item ${selectedCaseId === item._id ? 'selected' : ''}`}
                  key={item._id || item.caseId}
                  onClick={() => handleSelectCase(item._id)}
                >
                  <div>
                    <strong>{item.caseId}</strong>
                    <p>{renderStatusLabel(item.status)}</p>
                  </div>
                  <span className={`status-pill ${item.requiresHumanReview ? 'alert' : item.status === 'processing' ? 'processing' : 'ok'}`}>
                    {item.requiresHumanReview ? 'Review' : renderStatusLabel(item.status)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </section>}

        {(view === 'history' || view === 'reviews') && <section className="panel history-panel"><div className="panel-header"><h3>{view === 'reviews' ? 'Cases requiring review' : 'Screening history'}</h3><span className="case-state">{filteredCases.filter((item) => view !== 'reviews' || item.requiresHumanReview).length} records</span></div><div className="history-controls"><input placeholder="Search case ID or status" value={historyQuery} onChange={(e) => setHistoryQuery(e.target.value)} /><select value={historyFilter} onChange={(e) => setHistoryFilter(e.target.value)}><option value="all">All cases</option><option value="review">Needs review</option><option value="low">Low risk</option><option value="medium">Medium risk</option><option value="high">High risk</option><option value="critical">Critical risk</option></select></div><div className="activity-list">{filteredCases.filter((item) => view !== 'reviews' || item.requiresHumanReview).map((item) => <button type="button" className={`activity-item ${selectedCaseId === item._id ? 'selected' : ''}`} key={item._id || item.caseId} onClick={() => handleSelectCase(item._id)}><div><strong>{item.caseId || item._id}</strong><p>{renderStatusLabel(item.status)} · {new Date(item.createdAt || Date.now()).toLocaleString()}</p></div><span className={`status-pill ${item.requiresHumanReview ? 'alert' : 'ok'}`}>{item.requiresHumanReview ? 'Review' : 'Clear'}</span></button>)}{filteredCases.filter((item) => view !== 'reviews' || item.requiresHumanReview).length === 0 && <div className="empty-state">No matching screening records.</div>}</div></section>}

        {(view === 'overview' || view === 'screening' || activeResult) && <section className="results-panel panel" aria-busy={loading || caseLoading}>
          <div className="panel-header">
            <h3>Results</h3>
            {caseLoading ? <span className="case-state">Loading case...</span> : null}
          </div>

          {loading ? (
            <div className="empty-state loading-state"><span className="analysis-radar"><i /></span><p>Running OCR, validation, tampering, face, and risk checks…</p><small>Your screening pipeline is processing securely.</small></div>
          ) : !activeResult ? (
            <div className="empty-state">
              <p>No screening has been started yet.</p>
            </div>
          ) : (
            <>
            {activeResult.requiresHumanReview || activeResult.risk?.requiresHumanReview ? <div className="review-banner"><strong>Human review required</strong><span>This result is decision support only. Verify the evidence before taking action.</span></div> : null}
            <div className="results-grid">
              <div className="result-card">
                <h4>Extracted information</h4>
                <dl>
                  <div><dt>Document type</dt><dd>{activeResult.documentType || 'Unknown'}</dd></div>
                  <div><dt>OCR confidence</dt><dd>{(activeResult.ocr?.confidence ?? 0).toFixed(2)}</dd></div>
                </dl>
                <div className="field-list">
                  {activeResult.ocr?.fields ? Object.entries(activeResult.ocr.fields).map(([key, value]) => (
                    <div key={key} className="field-row">
                      <span>{formatFieldLabel(key)}</span>
                      <strong>{value || 'Not found'}</strong>
                    </div>
                  )) : null}
                </div>
                {activeResult.ocr?.warnings?.length > 0 ? (
                  <div className="notice warning" role="status">
                    {activeResult.ocr.warnings.map((warning) => <p key={warning}>{warning}</p>)}
                  </div>
                ) : null}
              </div>

              <div className="result-card">
                <h4>Validation</h4>
                <p className={`tag ${validationState.className}`}>
                  {validationState.label}
                </p>
                <ul>
                  {(activeResult.validation?.errors || []).map((item, index) => (
                    <li key={index}>{item.message || item.rule}</li>
                  ))}
                  {(activeResult.validation?.warnings || []).map((item, index) => (
                    <li key={index}>{item.message || item.rule}</li>
                  ))}
                  {!((activeResult.validation?.errors || []).length || (activeResult.validation?.warnings || []).length) && (
                    <li>No validation issues detected.</li>
                  )}
                </ul>
              </div>

              <div className="result-card">
                <h4>Tampering</h4>
                <p className={`tag ${activeResult.tampering?.tamperingDetected ? 'invalid' : activeResult.tampering?.assessment === 'clear' ? 'valid' : 'warning'}`}>
                  {activeResult.tampering?.tamperingDetected ? 'Review required' : activeResult.tampering?.assessment === 'clear' ? 'No indicators' : 'Inconclusive'}
                </p>
                <ul>
                  {(activeResult.tampering?.findings || []).length ? (
                    activeResult.tampering.findings.map((item, index) => (
                      <li key={index}>{item.description || item.type}</li>
                    ))
                  ) : (
                    <li>{activeResult.tampering?.assessment === 'clear' ? 'No suspicious tampering indicators detected.' : 'Image analysis is inconclusive; it does not establish that the document was altered.'}</li>
                  )}
                </ul>
              </div>

              <div className="result-card">
                <h4>Face verification</h4>
                <p className={`tag ${activeResult.face?.matchStatus === 'match' ? 'valid' : activeResult.face?.matchStatus === 'not_verified' ? 'warning' : 'invalid'}`}>
                  {activeResult.face?.matchStatus || 'not_verified'}
                </p>
                <ul>
                  <li>Detected in document: {String(activeResult.face?.faceDetectedInDocument ?? false)}</li>
                  <li>Detected in person photo: {String(activeResult.face?.faceDetectedInPerson ?? false)}</li>
                  <li>Similarity: {(activeResult.face?.similarity ?? 0).toFixed(2)}</li>
                  <li>Confidence: {(activeResult.face?.confidence ?? 0).toFixed(2)}</li>
                </ul>
              </div>

              <div className="result-card risk-card">
                <h4>Risk assessment</h4>
                <div className="risk-score-row">
                  <strong>{activeResult.risk?.riskScore ?? 0}</strong>
                  <span className={`risk-badge risk-${(activeResult.risk?.riskLevel || 'LOW').toLowerCase()}`}>
                    {renderRiskBadge(activeResult.risk?.riskLevel)}
                  </span>
                </div>
                <p>{activeResult.risk?.recommendation || 'Manual review recommended.'}</p>
                <ul>
                  {(activeResult.risk?.factors || []).length ? (
                    activeResult.risk.factors.map((factor, index) => (
                        <li key={index}>{typeof factor === 'string' ? factor : (factor.finding || factor.description || factor.category || 'Risk signal identified')}</li>
                    ))
                  ) : (
                    <li>No explicit risk factors identified.</li>
                  )}
                </ul>
              </div>
            </div></>
          )}
        </section>}
      </main>
    </div>
  );
}

export default App;
