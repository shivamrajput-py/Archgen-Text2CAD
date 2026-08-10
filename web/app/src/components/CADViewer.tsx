import { useState, lazy, Suspense, useEffect } from "react";
import "./CADViewer.css";
import type { ShadingMode } from "./CADViewerCanvas";

// ============================================
// LAZY-LOAD the heavy Canvas component
// ============================================
const CADViewerCanvas = lazy(() => import("./CADViewerCanvas"));

// ============================================
// TYPES
// ============================================
interface CADViewerProps {
  stlUrl: string | null;
  stepUrl?: string | null;
  isLoading: boolean;
  hasModel: boolean;
  showWireframe?: boolean;
  showAxes?: boolean;
  onDownloadSTL: () => void;
  onDownloadSTEP: () => void;
  onDownloadOBJ: () => void;
  onDownloadFCSTD?: () => void;
  onDownloadSVG?: () => void;
}

type ViewPreset = "front" | "back" | "top" | "bottom" | "left" | "right";

const VIEW_PRESETS: Record<ViewPreset, { position: [number, number, number]; label: string }> = {
  front:  { position: [0, 0, 12],    label: "Front" },
  back:   { position: [0, 0, -12],   label: "Back" },
  top:    { position: [0, 12, 0.01], label: "Top" },
  bottom: { position: [0, -12, 0.01],label: "Bottom" },
  left:   { position: [-12, 0, 0],   label: "Left" },
  right:  { position: [12, 0, 0],    label: "Right" },
};

// ============================================
// Canvas Loading Fallback
// ============================================
function CanvasLoadingFallback() {
  return (
    <div className="canvas-loading-fallback">
      <div className="modern-loader">
        <div className="loader-ring" />
        <div className="loader-text">INITIALIZING VIEWPORT</div>
      </div>
    </div>
  );
}

// ============================================
// Main CAD Viewer Component
// ============================================
export default function CADViewer({
  stlUrl,
  stepUrl,
  isLoading,
  onDownloadSTL,
  onDownloadSTEP,
  onDownloadOBJ,
  onDownloadFCSTD,
  onDownloadSVG,
  hasModel,
  showWireframe: externalWireframe = false,
  showAxes: externalAxes = false,
}: CADViewerProps) {
  const [modelLoaded, setModelLoaded] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [canvasKey, setCanvasKey] = useState(0); // force remount when URL changes

  // Viewer feature state
  const [showEdges, setShowEdges] = useState(true);
  const [showAxesLocal, setShowAxesLocal] = useState(externalAxes);
  const [shadingMode, setShadingMode] = useState<ShadingMode>("solid");
  const [isOrtho, setIsOrtho] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showShadows, setShowShadows] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);
  const [fitViewTrigger, setFitViewTrigger] = useState(0);
  const [cameraTarget, setCameraTarget] = useState<[number, number, number] | null>(null);

  const showAxesFinal = externalAxes || showAxesLocal;

  // *** KEY FIX: when the stlUrl/stepUrl changes (new model loaded),
  // reset modelLoaded + force canvas to remount so the new URL is fetched cleanly
  useEffect(() => {
    // Wrap in setTimeout to avoid React cascading renders warning
    setTimeout(() => {
      setModelLoaded(false);
      setModelError(null);
      setCanvasKey(k => k + 1);
    }, 0);
  }, [stlUrl, stepUrl]);

  const setView = (preset: ViewPreset) => setCameraTarget(VIEW_PRESETS[preset].position);

  const handleReset = () => {
    setCameraTarget([8, 6, 8]);
  };

  const cycleShadingMode = () => {
    setShadingMode(m => m === "solid" ? "wireframe" : m === "wireframe" ? "xray" : "solid");
  };

  const SHADING_LABELS: Record<ShadingMode, string> = {
    solid: "Solid",
    wireframe: "Wire",
    xray: "X-Ray",
  };

  return (
    <div className="cad-viewer">
      {/* ── Top Toolbar ── */}
      <div className="cad-viewer-toolbar">
        <div className="toolbar-left">
          <span className="viewer-title">
            <span className="viewer-dot" />
            Design Viewport
          </span>
          {modelLoaded && <span className="model-badge">Model Ready</span>}
        </div>

        <div className="toolbar-right">
          {hasModel && (
            <div className="download-buttons">
              <button className="btn-download" onClick={onDownloadSTL} disabled={!modelLoaded && !stlUrl} title="Download STL file">
                <DownloadIcon /> <span className="dl-label">STL</span>
              </button>
              <button className="btn-download btn-download-accent" onClick={onDownloadSTEP} disabled={!stepUrl} title="Download STEP file">
                <DownloadIcon /> <span className="dl-label">STEP</span>
              </button>
              <button className="btn-download" onClick={onDownloadOBJ} disabled={!modelLoaded && !stlUrl} title="Download OBJ file">
                <DownloadIcon /> <span className="dl-label">OBJ</span>
              </button>
              {onDownloadFCSTD && (
                <button className="btn-download btn-download-accent" onClick={onDownloadFCSTD} disabled={!stlUrl} title="Download FCStd file">
                  <DownloadIcon /> <span className="dl-label">FreeCAD</span>
                </button>
              )}
              {onDownloadSVG && (
                <button className="btn-download btn-download-accent" onClick={onDownloadSVG} disabled={!stlUrl} title="Download 2D Blueprint (SVG)">
                  <DownloadIcon /> <span className="dl-label">2D Draft</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── 3D Canvas ── */}
      <div className="cad-viewer-canvas">
        <Suspense fallback={<CanvasLoadingFallback />}>
          <CADViewerCanvas
            key={canvasKey}
            stlUrl={stlUrl}
            stepUrl={stepUrl}
            isLoading={isLoading}
            hasModel={hasModel}
            showWireframe={externalWireframe}
            showAxes={showAxesFinal}
            showEdges={showEdges}
            shadingMode={shadingMode}
            isOrtho={isOrtho}
            showGrid={showGrid}
            showShadows={showShadows}
            autoRotate={autoRotate}
            fitView={fitViewTrigger}
            cameraTarget={cameraTarget}
            onCameraReached={() => setCameraTarget(null)}
            onModelLoaded={() => { setModelLoaded(true); setModelError(null); }}
            onModelError={(e) => { setModelError(e); setModelLoaded(false); }}
            modelLoaded={modelLoaded}
          />
        </Suspense>

        {/* ── SPLIT CONTROLS BAR ── */}
        <div className="view-controls-bar">
          {/* LEFT: Camera view presets */}
          <div className="view-controls-group view-controls-views">
            <span className="vc-group-label">VIEW</span>
            {Object.entries(VIEW_PRESETS).map(([key, preset]) => (
              <button
                key={key}
                className="view-btn"
                onClick={() => setView(key as ViewPreset)}
                title={preset.label}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Separator */}
          <div className="vc-separator" />

          {/* RIGHT: Feature toggles */}
          <div className="view-controls-group view-controls-tools">
            <span className="vc-group-label">DISPLAY</span>

            <button
              className={`view-btn view-btn-icon ${showEdges ? "active" : ""}`}
              onClick={() => setShowEdges(!showEdges)}
              title={showEdges ? "Hide edge lines" : "Show edge lines"}
            >
              <EdgesIcon /> <span className="vb-label">Edges</span>
            </button>

            <button
              className={`view-btn view-btn-icon ${shadingMode !== "solid" ? "active" : ""}`}
              onClick={cycleShadingMode}
              title={`Shading: ${SHADING_LABELS[shadingMode]} — click to cycle Solid → Wire → X-Ray`}
            >
              <ShadingIcon mode={shadingMode} /> <span className="vb-label">{SHADING_LABELS[shadingMode]}</span>
            </button>



            <button
              className={`view-btn view-btn-icon ${showAxesLocal ? "active" : ""}`}
              onClick={() => setShowAxesLocal(!showAxesLocal)}
              title="Toggle origin XYZ axes"
            >
              <AxesIcon /> <span className="vb-label">Axes</span>
            </button>

            <button
              className={`view-btn view-btn-icon ${isOrtho ? "active" : ""}`}
              onClick={() => setIsOrtho(!isOrtho)}
              title={isOrtho ? "Switch to Perspective projection" : "Switch to Orthographic projection"}
            >
              <ProjectionIcon ortho={isOrtho} /> <span className="vb-label">{isOrtho ? "Ortho" : "Persp"}</span>
            </button>

            <button
              className="view-btn view-btn-icon"
              onClick={handleReset}
              title="Reset camera to default position"
            >
              <ResetIcon /> <span className="vb-label">Reset</span>
            </button>
          </div>

          {/* Separator */}
          <div className="vc-separator" />

          {/* SCENE group */}
          <div className="view-controls-group view-controls-scene">
            <span className="vc-group-label">SCENE</span>

            <button
              className={`view-btn view-btn-icon ${showGrid ? "active" : ""}`}
              onClick={() => setShowGrid(!showGrid)}
              title={showGrid ? "Hide grid" : "Show grid"}
            >
              <GridIcon /> <span className="vb-label">Grid</span>
            </button>

            <button
              className={`view-btn view-btn-icon ${showShadows ? "active" : ""}`}
              onClick={() => setShowShadows(!showShadows)}
              title={showShadows ? "Disable shadows" : "Enable shadows"}
            >
              <ShadowIcon /> <span className="vb-label">Shadow</span>
            </button>

            <button
              className={`view-btn view-btn-icon ${autoRotate ? "active" : ""}`}
              onClick={() => setAutoRotate(!autoRotate)}
              title={autoRotate ? "Stop auto-rotation" : "Start auto-rotation"}
            >
              <RotateIcon /> <span className="vb-label">Spin</span>
            </button>

            <button
              className="view-btn view-btn-icon"
              onClick={() => setFitViewTrigger(n => n + 1)}
              title="Zoom camera to fit the entire model"
            >
              <FitViewIcon /> <span className="vb-label">Fit</span>
            </button>
          </div>
        </div>

        {/* Loading overlay */}
        {isLoading && (
          <div className="loading-overlay">
            <div className="loading-content">
              <div className="spinner spinner-lg" />
              <div className="loading-text">
                <span className="loading-message-fade">Generating your design...</span>
              </div>
            </div>
          </div>
        )}

        {/* Error overlay */}
        {modelError && (
          <div className="error-overlay">
            <div className="error-content">
              <WarningIcon />
              <p>Failed to load 3D model</p>
              <p className="error-detail">The STL file may not be available yet</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================
// ICON COMPONENTS
// ============================================
function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ed8936" strokeWidth="1.5">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function EdgesIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="21" y2="15" />
      <line x1="9" y1="3" x2="9" y2="21" />
      <line x1="15" y1="3" x2="15" y2="21" />
    </svg>
  );
}

function ShadingIcon({ mode }: { mode: ShadingMode }) {
  if (mode === "wireframe") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3c2.5 3 4 5.7 4 9s-1.5 6-4 9" />
        <path d="M12 3c-2.5 3-4 5.7-4 9s1.5 6 4 9" />
        <path d="M3 12h18" />
      </svg>
    );
  }
  if (mode === "xray") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" strokeOpacity="0.4" />
        <circle cx="12" cy="12" r="4" />
        <line x1="12" y1="2" x2="12" y2="6" />
        <line x1="12" y1="18" x2="12" y2="22" />
        <line x1="2" y1="12" x2="6" y2="12" />
        <line x1="18" y1="12" x2="22" y2="12" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" fill="currentColor" fillOpacity="0.2" />
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

function AxesIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" strokeWidth="2">
      <line x1="4" y1="20" x2="4" y2="4" stroke="#ef4444" />
      <line x1="4" y1="20" x2="20" y2="20" stroke="#22c55e" />
      <line x1="4" y1="20" x2="12" y2="12" stroke="#3b82f6" />
    </svg>
  );
}

function ProjectionIcon({ ortho }: { ortho: boolean }) {
  if (ortho) {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="18" height="18" />
        <line x1="3" y1="9" x2="21" y2="9" />
        <line x1="3" y1="15" x2="21" y2="15" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 20L12 4l7 16" />
      <line x1="7" y1="14" x2="17" y2="14" />
    </svg>
  );
}

function ResetIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="21" y2="15" />
      <line x1="9" y1="3" x2="9" y2="21" />
      <line x1="15" y1="3" x2="15" y2="21" />
    </svg>
  );
}

function ShadowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function RotateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21.5 2v6h-6" />
      <path d="M21.34 15.57a10 10 0 1 1-.57-8.38" />
    </svg>
  );
}

function FitViewIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M15 3h6v6" />
      <path d="M9 21H3v-6" />
      <path d="M21 3l-7 7" />
      <path d="M3 21l7-7" />
    </svg>
  );
}
