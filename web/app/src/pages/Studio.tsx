// Archgen Studio - Text-to-CAD with Session History & Per-Prompt Model Browsing

import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import CADViewer from '../components/CADViewer';
import {
  generateCAD,
  clearConversation,
  CADWebSocket,
  submitFeedback,
  getCloudSessions,
  setCloudSessions,
  type CADGenerationResponse,
  type ProgressUpdate,
} from '../services/api';
import { API_BASE_URL } from '../config';
import './Studio.css';

// ============================================
// TYPES
// ============================================
interface ModelResult {
  sessionId: string;
  modelId?: string;
  stlUrl: string;
  stepUrl: string;
  fcstdUrl?: string;
  svgUrl?: string;
  score: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  status?: 'success' | 'error';
  score?: number;
  generationTime?: number;
  modelResult?: ModelResult; // present only when this msg generated a model
}

interface SavedSession {
  id: string;
  title: string;           // first prompt of the session
  createdAt: string;
  updatedAt: string;
  messages: Message[];
  lastSessionId: string | null; // backend session id
}

interface AdvancedSettings {
  modelName: string;
  maxIterations: number;
  minQualityScore: number;
  temperature: number;
  timeout: number;
}

const DEFAULT_SETTINGS: AdvancedSettings = {
  modelName: 'qwen/qwen3.5-plus-02-15',
  maxIterations: 5,
  minQualityScore: 0.7,
  temperature: 0.1,
  timeout: 120,
};

const EXAMPLE_PROMPTS = [
  "Design a gear with 24 teeth and module 2",
  "Create an L-shaped bracket with mounting holes",
  "Design a cantilever bridge spanning 50 meters",
  "Create a 3-blade wind turbine rotor",
];

const LS_KEY = 'archgen_sessions';

function loadSessions(): SavedSession[] {
  // One-time migration: clear stale sessions from before model persistence fix (v2)
  const MIGRATION_KEY = 'archgen_session_v';
  const CURRENT_VERSION = '3';
  if (localStorage.getItem(MIGRATION_KEY) !== CURRENT_VERSION) {
    localStorage.removeItem(LS_KEY);
    localStorage.removeItem('archgen_feedback');
    localStorage.setItem(MIGRATION_KEY, CURRENT_VERSION);
    return [];
  }
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveSessions(sessions: SavedSession[]) {
  try { 
    const jsonStr = JSON.stringify(sessions);
    localStorage.setItem(LS_KEY, jsonStr); 
    setCloudSessions(jsonStr).catch(err => {
      console.warn("Background cloud sync failed to push:", err);
    });
  } catch { /* quota */ }
}

// ============================================
// MAIN COMPONENT
// ============================================
export default function Studio() {
  const navigate = useNavigate();

  // Active session state
  const [currentSavedId, setCurrentSavedId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  // Viewer state — which model is displayed
  const [stlUrl, setStlUrl] = useState<string | null>(null);
  const [stepUrl, setStepUrl] = useState<string | null>(null);
  const [hasModel, setHasModel] = useState(false);
  const [activeModelIdx, setActiveModelIdx] = useState<number | null>(null); // index in messages of active model
  const [feedbackSent, setFeedbackSent] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem('archgen_feedback') || '{}'); } catch { return {}; }
  });
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);

  // Generation / UI state
  const [isGenerating, setIsGenerating] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [wsProgress, setWsProgress] = useState<ProgressUpdate | null>(null);
  const wsRef = useRef<CADWebSocket | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [settings, setSettings] = useState<AdvancedSettings>({ ...DEFAULT_SETTINGS });

  // Session history list
  const [sessions, setSessions] = useState<SavedSession[]>(loadSessions);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const settingsRef = useRef<HTMLDivElement>(null);

  // Auth gate and cloud sync
  useEffect(() => {
    const isAuth = localStorage.getItem('archgen_auth');
    if (!isAuth) {
      navigate('/signin');
    } else {
      // Pull sessions from SQLite cloud database
      getCloudSessions().then(data => {
        if (data && data.length > 5) {
          try {
            const parsed = JSON.parse(data);
            setSessions(parsed);
            localStorage.setItem(LS_KEY, data); // Ensure local matches cloud perfectly
          } catch (e) {
            console.error("Error parsing cloud session payload");
          }
        }
      }).catch(err => {
        console.warn("Could not sync cloud sessions pulling:", err.message);
      });
    }
  }, [navigate]);

  const loadingMessages = [
    "Analyzing your design intent...",
    "Generating design blueprint...",
    "Building the 3D model...",
    "Rendering geometry...",
    "Running quality checks...",
  ];

  useEffect(() => {
    if (!isGenerating) { setLoadingPhase(0); return; }
    const iv = setInterval(() => setLoadingPhase(p => (p + 1) % loadingMessages.length), 4000);
    return () => clearInterval(iv);
  }, [isGenerating, loadingMessages.length]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  // Persist current session to localStorage whenever messages change
  useEffect(() => {
    if (messages.length === 0) return;
    const now = new Date().toISOString();
    const title = messages[0]?.content?.slice(0, 60) || 'Untitled';

    setSessions(prev => {
      if (currentSavedId) {
        const updated = prev.map(s =>
          s.id === currentSavedId
            ? { ...s, messages, updatedAt: now, lastSessionId: sessionId }
            : s
        );
        saveSessions(updated);
        return updated;
      } else {
        const newSession: SavedSession = {
          id: `sess_${Date.now()}`,
          title,
          createdAt: now,
          updatedAt: now,
          messages,
          lastSessionId: sessionId,
        };
        setCurrentSavedId(newSession.id);
        const updated = [newSession, ...prev];
        saveSessions(updated);
        return updated;
      }
    });
  }, [messages, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load a saved session
  const handleLoadSession = useCallback((saved: SavedSession) => {
    setCurrentSavedId(saved.id);
    setSessionId(saved.lastSessionId);
    setMessages(saved.messages);
    setShowSidebar(false);

    // Find the last model result in that session and display it
    const modelMsgs = saved.messages.filter(m => m.modelResult);
    if (modelMsgs.length > 0) {
      const last = modelMsgs[modelMsgs.length - 1].modelResult!;
      setStlUrl(last.stlUrl);
      setStepUrl(last.stepUrl);
      setHasModel(true);
      setActiveModelIdx(saved.messages.lastIndexOf(modelMsgs[modelMsgs.length - 1]));
    } else {
      setStlUrl(null);
      setStepUrl(null);
      setHasModel(false);
      setActiveModelIdx(null);
    }
  }, []);

  // Start a brand new chat
  const handleNewSession = useCallback(async () => {
    if (sessionId) {
      try { await clearConversation(sessionId); } catch { /* ignore */ }
    }
    setMessages([]);
    setSessionId(null);
    setCurrentSavedId(null);
    setStlUrl(null);
    setStepUrl(null);
    setHasModel(false);
    setActiveModelIdx(null);
    setShowSidebar(false);
  }, [sessionId]);

  // Load a specific model result from any message in the current session
  const handleViewModelAt = useCallback((msgIdx: number, result: ModelResult) => {
    setStlUrl(result.stlUrl);
    setStepUrl(result.stepUrl);
    setHasModel(true);
    setActiveModelIdx(msgIdx);
  }, []);

  // Submit feedback for a model
  const handleFeedback = useCallback(async (modelId: string) => {
    if (!feedbackRating || feedbackSubmitting) return;
    setFeedbackSubmitting(true);
    try {
      await submitFeedback(modelId, {
        rating: feedbackRating,
        comment: feedbackComment || undefined,
        useful: feedbackRating >= 3,
      });
      const updated = { ...feedbackSent, [modelId]: true };
      setFeedbackSent(updated);
      localStorage.setItem('archgen_feedback', JSON.stringify(updated));
      setFeedbackRating(0);
      setFeedbackComment('');
    } catch (err) {
      console.error('Feedback error:', err);
    } finally {
      setFeedbackSubmitting(false);
    }
  }, [feedbackRating, feedbackComment, feedbackSent, feedbackSubmitting]);

  // Delete a saved session
  const handleDeleteSession = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setSessions(prev => {
      const updated = prev.filter(s => s.id !== id);
      saveSessions(updated);
      return updated;
    });
    if (currentSavedId === id) {
      setMessages([]);
      setCurrentSavedId(null);
      setSessionId(null);
      setStlUrl(null);
      setStepUrl(null);
      setHasModel(false);
      setActiveModelIdx(null);
    }
  }, [currentSavedId]);

  // Send a prompt
  const handleSendMessage = useCallback(async (prompt: string) => {
    if (!prompt.trim() || isGenerating) return;

    const limitStr = localStorage.getItem('archgen_limit');
    if (limitStr && parseInt(limitStr) <= 0) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `⚠ Quota exceeded. You have 0 prompts remaining. Please contact support to increase your limit.`,
        timestamp: new Date().toISOString(),
        status: 'error',
      }]);
      return;
    }

    const userMsg: Message = {
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsGenerating(true);
    setWsProgress(null);

    // Pre-create a session id so we can connect WS before the HTTP request
    const preSessionId = sessionId || crypto.randomUUID();
    if (!sessionId) setSessionId(preSessionId);

    // Connect WebSocket immediately for real-time progress during generation
    if (wsRef.current) { wsRef.current.disconnect(); wsRef.current = null; }
    const ws = new CADWebSocket(
      preSessionId,
      (update: ProgressUpdate) => setWsProgress(update),
      (err) => console.error('WS error:', err),
      () => { wsRef.current = null; }
    );
    ws.connect();
    wsRef.current = ws;

    try {
      const result: CADGenerationResponse = await generateCAD({
        prompt: prompt.trim(),
        session_id: preSessionId,
        model_name: settings.modelName,
        max_iterations: settings.maxIterations,
        min_quality_score: settings.minQualityScore,
        temperature: settings.temperature,
        timeout: settings.timeout,
      });

      setSessionId(result.session_id);

      const modelResult: ModelResult | undefined = result.success && result.session_id ? {
        sessionId: result.session_id,
        modelId: result.model_id,
        stlUrl: result.model_id ? `${API_BASE_URL}/download/model/${result.model_id}/stl` : `${API_BASE_URL}/download/${result.session_id}/stl`,
        stepUrl: result.model_id ? `${API_BASE_URL}/download/model/${result.model_id}/step` : `${API_BASE_URL}/download/${result.session_id}/step`,
        fcstdUrl: result.model_id ? `${API_BASE_URL}/download/model/${result.model_id}/fcstd` : `${API_BASE_URL}/download/${result.session_id}/fcstd`,
        svgUrl: result.model_id ? `${API_BASE_URL}/download/model/${result.model_id}/svg` : `${API_BASE_URL}/download/${result.session_id}/svg`,
        score: result.final_score,
      } : undefined;

      const assistantMsg: Message = {
        role: 'assistant',
        content: result.success
          ? `✓ Generated your CAD model! Quality score: ${Math.round(result.final_score * 100)}%. View it in the 3D panel or download the files.`
          : `⚠ ${result.error_summary || 'Generation encountered issues. Please try again with more details.'}`,
        timestamp: new Date().toISOString(),
        status: result.success ? 'success' : 'error',
        score: result.final_score,
        generationTime: result.generation_time_seconds,
        modelResult,
      };

      setMessages(prev => {
        const next = [...prev, assistantMsg];
        // Auto-display the latest model
        if (modelResult) {
          setStlUrl(modelResult.stlUrl);
          setStepUrl(modelResult.stepUrl);
          setHasModel(true);
          setActiveModelIdx(next.length - 1);
        }
        return next;
      });

      // Update local storage limit optimistically
      if (result.success) {
        const currentLimit = localStorage.getItem('archgen_limit');
        if (currentLimit) {
          localStorage.setItem('archgen_limit', (parseInt(currentLimit) - 1).toString());
        }
      }
    } catch (err) {
      const isAuthError = err instanceof Error && (err.name === 'AuthError' || err.message.includes('403') || err.message.includes('Quota'));
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: isAuthError 
          ? `⚠ Quota exceeded or authentication error. Please contact support.`
          : `⚠ Error: ${err instanceof Error ? err.message : 'Unknown error'}. Please try again.`,
        timestamp: new Date().toISOString(),
        status: 'error',
      }]);
    } finally {
      setIsGenerating(false);
      setWsProgress(null);
      if (wsRef.current) { wsRef.current.disconnect(); wsRef.current = null; }
    }
  }, [isGenerating, sessionId, settings]);

  // Download handlers — use whichever model is active
  const handleDownloadSTL = useCallback(() => {
    if (stlUrl) window.open(stlUrl, '_blank');
  }, [stlUrl]);
  const handleDownloadSTEP = useCallback(() => {
    if (stepUrl) window.open(stepUrl, '_blank');
  }, [stepUrl]);
  const handleDownloadOBJ = useCallback(() => {
    if (activeModelIdx !== null && messages[activeModelIdx]?.modelResult?.modelId) {
      window.open(`${API_BASE_URL}/download/model/${messages[activeModelIdx].modelResult.modelId}/obj`, '_blank');
    } else if (sessionId) {
      window.open(`${API_BASE_URL}/download/${sessionId}/obj`, '_blank');
    }
  }, [sessionId, messages, activeModelIdx]);
  const handleDownloadFCSTD = useCallback(() => {
    if (activeModelIdx !== null && messages[activeModelIdx]?.modelResult?.modelId) {
      window.open(`${API_BASE_URL}/download/model/${messages[activeModelIdx].modelResult.modelId}/fcstd`, '_blank');
    } else if (sessionId) {
      window.open(`${API_BASE_URL}/download/${sessionId}/fcstd`, '_blank');
    }
  }, [sessionId, messages, activeModelIdx]);
  const handleDownloadSVG = useCallback(() => {
    if (activeModelIdx !== null && messages[activeModelIdx]?.modelResult?.modelId) {
      window.open(`${API_BASE_URL}/download/model/${messages[activeModelIdx].modelResult.modelId}/svg`, '_blank');
    } else if (sessionId) {
      window.open(`${API_BASE_URL}/download/${sessionId}/svg`, '_blank');
    }
  }, [sessionId, messages, activeModelIdx]);


  const handleSubmit = (e: React.FormEvent) => { e.preventDefault(); handleSendMessage(inputValue); };
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(inputValue); }
  };

  useEffect(() => {
    function outside(ev: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(ev.target as Node)) setShowSettings(false);
    }
    if (showSettings) { document.addEventListener('mousedown', outside); return () => document.removeEventListener('mousedown', outside); }
  }, [showSettings]);

  // Format date for history
  const fmtDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="studio-app">
      {/* ========== HEADER ========== */}
      <header className="studio-header">
        <div className="header-left">
          <button className="back-btn" onClick={() => navigate('/')} title="Back to home">
            <ArrowLeftIcon />
          </button>
          <div className="logo">
            <div style={{ width: 28, height: 28, borderRadius: 8, background: 'linear-gradient(135deg, #5DA9E9, #667eea)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ArchgenLogo />
            </div>
            <span className="logo-text" style={{ background: 'linear-gradient(135deg, #5DA9E9, #667eea)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>ARCHGEN</span>
          </div>
        </div>

        <nav className="header-nav">
          <a href="#" className="nav-link active">Studio</a>
          <a href="/services" className="nav-link">Services</a>
          <a href="/demo" className="nav-link">View Examples</a>
        </nav>

        <div className="header-right">
          {localStorage.getItem('archgen_auth') && (
            <div className="limit-badge text-xs px-3 py-1 bg-[#11161D] text-[#5DA9E9] border border-white/10 rounded-full flex items-center gap-2 mr-2">
              <div className="w-1.5 h-1.5 rounded-full bg-[#5DA9E9] animate-pulse"></div>
              {localStorage.getItem('archgen_limit') || '0'} prompts remaining
            </div>
          )}
          
          {/* History toggle */}
          <button
            className={`settings-btn ${showSidebar ? 'active' : ''}`}
            onClick={() => setShowSidebar(s => !s)}
            title="Session History"
          >
            <HistoryIcon />
          </button>

          {/* Settings */}
          <div className="settings-wrapper" ref={settingsRef}>
            <button className={`settings-btn ${showSettings ? 'active' : ''}`} onClick={() => setShowSettings(!showSettings)} title="Advanced Settings">
              <SettingsIcon />
            </button>
            {showSettings && (
              <div className="settings-panel">
                <div className="settings-panel-header">
                  <span>Advanced Settings</span>
                  <button className="settings-close-btn" onClick={() => setShowSettings(false)}>×</button>
                </div>
                <div className="settings-group">
                  <label className="settings-label">
                    Model
                    <input type="text" className="settings-input" value={settings.modelName} onChange={(e) => setSettings(s => ({ ...s, modelName: e.target.value }))} placeholder="e.g. anthropic/claude-sonnet-4" />
                  </label>
                </div>
                <div className="settings-group">
                  <label className="settings-label">
                    Max Iterations
                    <div className="settings-range-row">
                      <input type="range" className="settings-range" min={1} max={10} step={1} value={settings.maxIterations} onChange={(e) => setSettings(s => ({ ...s, maxIterations: parseInt(e.target.value) }))} />
                      <span className="settings-range-value">{settings.maxIterations}</span>
                    </div>
                  </label>
                </div>
                <div className="settings-group">
                  <label className="settings-label">
                    Quality Threshold
                    <div className="settings-range-row">
                      <input type="range" className="settings-range" min={0.3} max={0.95} step={0.05} value={settings.minQualityScore} onChange={(e) => setSettings(s => ({ ...s, minQualityScore: parseFloat(e.target.value) }))} />
                      <span className="settings-range-value">{(settings.minQualityScore * 100).toFixed(0)}%</span>
                    </div>
                  </label>
                </div>
                <div className="settings-group">
                  <label className="settings-label">
                    Temperature
                    <div className="settings-range-row">
                      <input type="range" className="settings-range" min={0} max={1} step={0.05} value={settings.temperature} onChange={(e) => setSettings(s => ({ ...s, temperature: parseFloat(e.target.value) }))} />
                      <span className="settings-range-value">{settings.temperature.toFixed(2)}</span>
                    </div>
                  </label>
                </div>
                <div className="settings-group">
                  <label className="settings-label">
                    Timeout (seconds)
                    <input type="number" className="settings-input" min={30} max={600} value={settings.timeout} onChange={(e) => setSettings(s => ({ ...s, timeout: parseInt(e.target.value) || 120 }))} />
                  </label>
                </div>
                <button className="settings-reset-btn" onClick={() => setSettings({ ...DEFAULT_SETTINGS })}>Reset to Defaults</button>
              </div>
            )}
          </div>

          <div className="user-avatar" title="User"><UserIcon /></div>
        </div>
      </header>

      {/* ========== MAIN LAYOUT ========== */}
      <div className="studio-body">

        {/* ── SESSION HISTORY SIDEBAR ── */}
        <aside className={`history-sidebar ${showSidebar ? 'open' : ''}`}>
          <div className="history-sidebar-header">
            <span className="history-sidebar-title">
              <HistoryIcon /> Session History
            </span>
            <button className="history-new-btn" onClick={handleNewSession} title="New session">
              <PlusIcon /> New
            </button>
          </div>

          <div className="history-list">
            {sessions.length === 0 ? (
              <div className="history-empty">No saved sessions yet.<br />Start designing to save automatically.</div>
            ) : (
              sessions.map(s => (
                <div
                  key={s.id}
                  role="button"
                  tabIndex={0}
                  className={`history-item ${s.id === currentSavedId ? 'active' : ''}`}
                  onClick={() => handleLoadSession(s)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLoadSession(s)}
                >
                  <div className="history-item-top">
                    <span className="history-item-title">{s.title}</span>
                    <button
                      className="history-item-delete"
                      onClick={(e) => handleDeleteSession(e, s.id)}
                      title="Delete session"
                    >
                      ×
                    </button>
                  </div>
                  <div className="history-item-meta">
                    {fmtDate(s.updatedAt)} · {s.messages.filter(m => m.role === 'user').length} prompt{s.messages.filter(m => m.role === 'user').length !== 1 ? 's' : ''}
                  </div>
                  <div className="history-item-preview">
                    {s.messages.filter(m => m.modelResult).length} model{s.messages.filter(m => m.modelResult).length !== 1 ? 's' : ''} generated
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>

        {/* ── MAIN CONTENT ── */}
        <main className="studio-main">
          {/* 3D Viewer */}
          <div className="viewer-container">
            <CADViewer
              stlUrl={stlUrl}
              stepUrl={stepUrl}
              isLoading={isGenerating && !wsProgress?.details?.downloading}
              onDownloadSTL={handleDownloadSTL}
              onDownloadSTEP={handleDownloadSTEP}
              onDownloadOBJ={handleDownloadOBJ}
              onDownloadFCSTD={handleDownloadFCSTD}
              onDownloadSVG={handleDownloadSVG}
              hasModel={hasModel}
              showWireframe={false}
            />
          </div>

          {/* Chat Panel */}
          <div className="chat-panel">
            <div className="chat-header">
              <div className="chat-header-icon"><ArcIcon /></div>
              <span className="chat-header-title">ARC</span>
              <button className="btn-icon" title="New chat" onClick={handleNewSession}><PlusIcon /></button>
            </div>

            <div className="chat-messages">
              {messages.length === 0 ? (
                <div className="chat-welcome">
                  <h3>What would you like to design?</h3>
                  <p>Describe your CAD model and I'll generate it for you.</p>
                  <div className="example-prompts">
                    {EXAMPLE_PROMPTS.map((prompt, idx) => (
                      <button key={idx} className="example-prompt" onClick={() => handleSendMessage(prompt)}>{prompt}</button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                      <div className={`message-content ${msg.status || ''}`}>
                        {msg.content}
                        {msg.generationTime && (
                          <span className="message-meta">
                            Generated in {msg.generationTime >= 60
                              ? `${(msg.generationTime / 60).toFixed(1)} min`
                              : `${msg.generationTime.toFixed(0)}s`
                            }
                          </span>
                        )}
                        {/* Per-prompt model viewer button */}
                        {msg.modelResult && (
                          <button
                            className={`view-model-btn ${activeModelIdx === idx ? 'view-model-btn-active' : ''}`}
                            onClick={() => handleViewModelAt(idx, msg.modelResult!)}
                            title="Load this design into the viewport"
                          >
                            {activeModelIdx === idx ? (
                              <><ViewActiveIcon /> Viewing in 3D</>
                            ) : (
                              <><ViewIcon /> View this design</>
                            )}
                          </button>
                        )}
                        {/* Inline feedback card */}
                        {msg.modelResult?.modelId && msg.status === 'success' && !feedbackSent[msg.modelResult.modelId] && (
                          <div className="feedback-card">
                            <span className="feedback-label">Rate this design</span>
                            <div className="feedback-stars">
                              {[1,2,3,4,5].map(star => (
                                <button
                                  key={star}
                                  className={`star-btn ${feedbackRating >= star ? 'star-active' : ''}`}
                                  onClick={() => setFeedbackRating(star)}
                                  title={`${star} star${star > 1 ? 's' : ''}`}
                                >&#9733;</button>
                              ))}
                            </div>
                            {feedbackRating > 0 && (
                              <>
                                <input
                                  className="feedback-input"
                                  placeholder="Any thoughts? (optional)"
                                  value={feedbackComment}
                                  onChange={e => setFeedbackComment(e.target.value)}
                                  maxLength={200}
                                />
                                <button
                                  className="feedback-submit"
                                  onClick={() => handleFeedback(msg.modelResult!.modelId!)}
                                  disabled={feedbackSubmitting}
                                >
                                  {feedbackSubmitting ? 'Sending...' : 'Submit'}
                                </button>
                              </>
                            )}
                          </div>
                        )}
                        {msg.modelResult?.modelId && feedbackSent[msg.modelResult.modelId] && (
                          <span className="feedback-thanks">Thanks for your feedback!</span>
                        )}
                      </div>
                    </div>
                  ))}

                  {isGenerating && (
                    <div className="message assistant">
                      <div className="message-content loading-message">
                        <div className="loading-dots"><span /><span /><span /></div>
                        <span className="loading-text-fade">
                          {wsProgress ? wsProgress.message : loadingMessages[loadingPhase]}
                        </span>
                        {wsProgress && (
                          <div className="ws-progress-bar-wrapper">
                            <div className="ws-progress-bar" style={{ width: `${Math.round((wsProgress.progress || 0) * 100)}%` }} />
                            <span className="ws-progress-pct">{Math.round((wsProgress.progress || 0) * 100)}%</span>
                          </div>
                        )}
                        {wsProgress && wsProgress.iteration && wsProgress.max_iterations && wsProgress.max_iterations > 1 && (
                          <span className="ws-iter-badge">Pass {wsProgress.iteration}/{wsProgress.max_iterations}</span>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-input-container" onSubmit={handleSubmit}>
              <textarea
                className="chat-input"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe what you want to design..."
                disabled={isGenerating}
                rows={1}
              />
              <button type="submit" className="send-btn" disabled={isGenerating || !inputValue.trim()}>
                {isGenerating ? <LoaderIcon /> : <SendIcon />}
              </button>
            </form>

            <div className="chat-footer">
              <span>ARC can make mistakes. Always verify dimensions.</span>
            </div>
          </div>
        </main>
      </div>


    </div>
  );
}

// ============================================
// ICONS
// ============================================
function ArrowLeftIcon() {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>;
}
function ArchgenLogo() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><path d="M3 21l9-18 9 18" /><path d="M6 15h12" /></svg>;
}
function SettingsIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
}
function UserIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>;
}
function ArcIcon() {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 21l9-18 9 18" /><path d="M6 15h12" /></svg>;
}
function PlusIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>;
}
function SendIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>;
}
function LoaderIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin"><circle cx="12" cy="12" r="10" strokeOpacity="0.25" /><path d="M12 2a10 10 0 0 1 10 10" strokeOpacity="1" /></svg>;
}

function HistoryIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 .49-3.51" /></svg>;
}
function ViewIcon() {
  return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>;
}
function ViewActiveIcon() {
  return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" fill="currentColor" /></svg>;
}
