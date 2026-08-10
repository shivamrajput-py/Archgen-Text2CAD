import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Layers,
  Boxes,
  PenTool,
  Building2,
  Cog,
  BrainCircuit,
  Sparkles,
  ChevronDown,
  Check,
  Activity,
  BarChart,
} from 'lucide-react';
import './ArchgenCAD.css';

// ============================================
// DATA
// ============================================
const SOFTWARE_SUITE = [
  {
    icon: Cog,
    name: 'Archgen Mechanical',
    replaces: 'Mechanical / Product Design',
    description: 'From 2D drafting to 3D parametric modeling, sheet metal, and generative engineering.',
    status: 'In Development',
    color: '#5DA9E9',
  },
  {
    icon: Building2,
    name: 'Archgen BIM',
    replaces: 'AEC / Regulation-Aware Architecture',
    description: 'Text-to-BIM layouts, structural design, and architectural compliance seamlessly automated.',
    status: 'Coming Soon',
    color: '#667eea',
  },
  {
    icon: BrainCircuit,
    name: 'Archgen PCB',
    replaces: 'Electronics & Semiconductor (EDA)',
    description: 'Text-to-circuit design, PCB layout, and schematic capture logic with AI-native synthesis.',
    status: 'Coming Soon',
    color: '#48bb78',
  },
  {
    icon: Activity,
    name: 'Archgen CAE',
    replaces: 'AI-Native Physics Validation',
    description: 'Automated simulation loops, stress validation, and deep material physics connected directly to geometry.',
    status: 'Coming Soon',
    color: '#ed8936',
  },
];

const CAPABILITIES = [
  { icon: PenTool, label: '2D Drafting', detail: 'Precision 2D workflows' },
  { icon: Boxes, label: '3D Modeling', detail: 'Parametric solid modeling' },
  { icon: Cog, label: 'Mechanical', detail: 'Assemblies & simulation' },
  { icon: Building2, label: 'Architectural', detail: 'BIM-ready design' },
  { icon: Layers, label: 'Structural', detail: 'Load analysis & optimization' },
  { icon: BrainCircuit, label: 'AI-Native', detail: 'Built with AI at the core' },
  { icon: Activity, label: 'Physics Validation', detail: 'Stress, strain & CAE workflows' },
  { icon: BarChart, label: 'Material Analysis', detail: 'Cost & material requirements estimation' },
];

const FEATURES = [
  'Natural language to CAD generation',
  'AI-powered design suggestions',
  'Real-time parametric optimization',
  'Multi-format export (STL, STEP, DWG, IGES)',
  'Cloud collaboration & version control',
  'Plugin architecture for extensibility',
  'Open-source architecture',
  'Cross-platform (Windows, Mac, Linux)',
];

// ============================================
// ANIMATED COUNTER
// ============================================
function useCountUp(end: number, duration: number = 2000, start: boolean = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!start) return;
    let startTime: number;
    let frame: number;
    const animate = (ts: number) => {
      if (!startTime) startTime = ts;
      const progress = Math.min((ts - startTime) / duration, 1);
      setCount(Math.floor(progress * end));
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [end, duration, start]);
  return count;
}

// ============================================
// MAIN COMPONENT
// ============================================
export default function ArchgenCAD() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [statsVisible, setStatsVisible] = useState(false);
  const statsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setStatsVisible(true); },
      { threshold: 0.3 }
    );
    if (statsRef.current) observer.observe(statsRef.current);
    return () => observer.disconnect();
  }, []);

  const handleWaitlist = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) setSubmitted(true);
  };

  const stat1 = useCountUp(10, 2000, statsVisible);
  const stat2 = useCountUp(5, 2000, statsVisible);
  const stat3 = useCountUp(100, 2000, statsVisible);

  return (
    <div className="archgencad-page">
      {/* Floating Particles */}
      <div className="particles-container">
        {[...Array(12)].map((_, i) => (
          <div key={i} className="particle" style={{ left: `${(i * 8.3) % 100}%`, animationDelay: `${i * 1.3}s` }} />
        ))}
      </div>

      {/* Navigation */}
      <nav className="acad-nav">
        <button className="acad-back" onClick={() => navigate('/')}>
          <ArrowLeft size={18} />
          <span>Back</span>
        </button>
        <div className="acad-nav-brand">
          <div className="acad-logo-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <path d="M3 21l9-18 9 18" /><path d="M6 15h12" />
            </svg>
          </div>
          <span className="acad-logo-text">ARCHGEN</span>
        </div>
        <a href="/studio" className="acad-try-studio">
          Open Studio <ArrowRight size={14} />
        </a>
      </nav>

      {/* ============================================
          HERO SECTION
          ============================================ */}
      <section className="acad-hero">
        {/* Background */}
        <div className="acad-hero-bg">
          <div className="acad-grid-bg" />
          <div className="acad-glow-1" />
          <div className="acad-glow-2" />
          <div className="acad-glow-3" />
        </div>

        <div className="acad-hero-content visible">
          {/* Badge */}
          <div className="acad-badge">
            <Sparkles size={14} />
            <span>Redefining the CAD Industry</span>
          </div>

          {/* Title */}
          <h1 className="acad-title" style={{ fontSize: '3.5rem', lineHeight: '1.2' }}>
            <span className="acad-title-line">India's First Generative AI</span>
            <span className="acad-title-line acad-title-gradient">Platform for Physical Products.</span>
          </h1>

          {/* Subtitle */}
          <p className="acad-subtitle" style={{ fontSize: '1.2rem', maxWidth: '800px', margin: '0 auto 2rem' }}>
            Powered by the <strong>Physora Engine</strong>. Turn natural language into production-ready CAD with real-time physics simulation and parametric history.
            <br /><br />
            Archgen is an AI-native engineering software engineered from the ground up—not a plugin on legacy tools. <strong>Just like Cursor transformed coding, Archgen transforms physical engineering.</strong>
          </p>

          {/* Intro Section - Physora Showcase */}
          <div className="physora-showcase" style={{
            background: 'rgba(15, 25, 35, 0.6)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '16px',
            padding: '24px',
            margin: '0 auto 3rem',
            maxWidth: '700px',
            backdropFilter: 'blur(10px)',
            textAlign: 'left'
          }}>
             <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: '#ed8936', fontWeight: 'bold' }}>
               <Activity size={20} />
               <span>Physora Engine Output</span>
             </div>
             <div style={{ background: '#0D1117', padding: '16px', borderRadius: '8px', marginBottom: '16px', fontFamily: 'monospace', fontSize: '14px', border: '1px solid #2D3748' }}>
                <span style={{ color: '#48bb78' }}>&gt;</span> "Design a modular cantilever bridge spanning 80m with load rating 50kN/m²"
             </div>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '14px', color: '#A0AEC0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="#48bb78" /> Natural Language Parsing</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="#48bb78" /> Parametric Script Generation</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="#48bb78" /> Auto Physics Validation</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} color="#48bb78" /> Solid B-Rep (STEP) Export</div>
             </div>
          </div>

          {/* CTA */}
          <div className="acad-hero-actions">
            {!submitted ? (
              <form className="acad-waitlist-form" onSubmit={handleWaitlist}>
                <input
                  type="email"
                  className="acad-email-input"
                  placeholder="your@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <button type="submit" className="acad-waitlist-btn">
                  Join Waitlist <ArrowRight size={16} />
                </button>
              </form>
            ) : (
              <div className="acad-waitlist-success">
                <Check size={20} />
                <span>You're on the list! We'll notify you when ArchgenCAD launches.</span>
              </div>
            )}
          </div>

          {/* Scroll Indicator */}
          <div className="acad-scroll-indicator">
            <ChevronDown size={20} />
          </div>
        </div>
      </section>

      {/* ============================================
          STATS BAR
          ============================================ */}
      <section className="acad-stats" ref={statsRef}>
        <div className="acad-stats-grid">
          <div className="acad-stat">
            <span className="acad-stat-number">{stat1}x</span>
            <span className="acad-stat-label">Faster Design Iterations</span>
          </div>
          <div className="acad-stat">
            <span className="acad-stat-number">{stat2}</span>
            <span className="acad-stat-label">Software Products Planned</span>
          </div>
          <div className="acad-stat">
            <span className="acad-stat-number">{stat3}%</span>
            <span className="acad-stat-label">AI-Native Architecture</span>
          </div>
        </div>
      </section>

      {/* ============================================
          SOFTWARE SUITE
          ============================================ */}
      <section className="acad-suite">
        <div className="acad-section-header">
          <span className="acad-section-badge">The Suite</span>
          <h2>One Vision. <span className="gradient-text">Multiple Platforms.</span></h2>
          <p>
            We're not building AI features for existing software. We're building entirely new 
            AI-native platforms — covering the full spectrum from mechanical to architectural design.
          </p>
        </div>

        <div className="acad-suite-grid">
          {SOFTWARE_SUITE.map((sw, idx) => (
            <div key={idx} className="acad-suite-card" style={{ '--card-color': sw.color } as React.CSSProperties}>
              <div className="acad-suite-card-icon">
                <sw.icon size={28} />
              </div>
              <div className="acad-suite-card-status">{sw.status}</div>
              <h3>{sw.name}</h3>
              <p className="acad-suite-card-replaces">{sw.replaces}</p>
              <p className="acad-suite-card-desc">{sw.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ============================================
          CAPABILITIES
          ============================================ */}
      <section className="acad-capabilities">
        <div className="acad-section-header">
          <span className="acad-section-badge">Coverage</span>
          <h2>Every Discipline. <span className="gradient-text">Every Scale.</span></h2>
          <p>
            From small mechanical parts to massive structural projects — Archgen covers the entire 
            engineering design spectrum.
          </p>
        </div>

        <div className="acad-cap-grid">
          {CAPABILITIES.map((cap, idx) => (
            <div key={idx} className="acad-cap-card">
              <div className="acad-cap-icon">
                <cap.icon size={24} />
              </div>
              <h4>{cap.label}</h4>
              <p>{cap.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ============================================
          WORKBENCH SECTION
          ============================================ */}
      <section className="acad-workbench">
        <div className="acad-workbench-content">
          <div className="acad-section-header">
            <span className="acad-section-badge">Available Now</span>
            <h2>ArchgenCAD <span className="gradient-text">Integrations</span></h2>
            <p>
              Experience the power of AI-native engineering everywhere. 
              Our vision is to bring seamless, natural-language generation natively into your favorite CAD, BIM, and EDA platforms.
            </p>
          </div>
          
          <div className="acad-workbench-grid">
            {/* Left: Features & Install */}
            <div className="acad-workbench-info glass-card">
              <div className="acad-workbench-features">
                <h3>Why use Archgen Integrations?</h3>
                <ul className="acad-proof-list">
                  <li><Check size={16} /> <strong>Universal Applicability</strong> — Go from intent to editable designs in seconds, across any discipline.</li>
                  <li><Check size={16} /> <strong>Parametric History</strong> — Edits are non-destructive, translating cleanly to native tool trees.</li>
                  <li><Check size={16} /> <strong>Seamless Interop</strong> — Start in the browser, polish in the professional tool of your choice.</li>
                  <li><Check size={16} /> <strong>Open Core</strong> — Leveraging standardized formats to bridge AI and industry software.</li>
                </ul>
              </div>

              <div className="acad-workbench-install">
                <h3>Try the ArchGen Plugin</h3>
                <div className="acad-terminal">
                  <div className="acad-terminal-dots">
                    <span /><span /><span />
                  </div>
                  <div className="acad-terminal-body">
                    <p className="t-dim"># Clone the reference integration into your Mod directory</p>
                    <p><span className="t-green">$</span> cd ~/ArchGen/plugins</p>
                    <p><span className="t-green">$</span> git clone https://github.com/archgen/workbench.git ArchgenCAD</p>
                    <br/>
                    <p className="t-dim"># Future plugins for Revit, SolidWorks, and Altium are coming soon.</p>
                  </div>
                </div>
              </div>
              
              <div className="acad-workbench-actions">
                <a href="https://github.com/archgen/workbench" target="_blank" rel="noreferrer" className="btn-secondary">
                  View Reference on GitHub
                </a>
              </div>
            </div>

            {/* Right: Image Placeholder */}
            <div className="acad-workbench-visual">
              <div className="acad-image-placeholder">
                <div className="placeholder-content" style={{gap: '12px'}}>
                  <div className="placeholder-icon">📸</div>
                  <p style={{fontSize: '18px', fontWeight: 'bold', color: 'white'}}>Archgen Integrations</p>
                  <span className="t-dim">Bringing AI inside your professional CAD ecosystem.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>


      {/* ============================================
          FEATURES LIST
          ============================================ */}
      <section className="acad-features">
        <div className="acad-section-header">
          <span className="acad-section-badge">Features</span>
          <h2>Built for <span className="gradient-text">Engineers</span></h2>
        </div>

        <div className="acad-features-grid">
          {FEATURES.map((feature, idx) => (
            <div key={idx} className="acad-feature-item">
              <div className="acad-feature-check">
                <Check size={14} />
              </div>
              <span>{feature}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ============================================
          FINAL CTA
          ============================================ */}
      <section className="acad-final-cta">
        <div className="acad-final-glow" />
        <div className="acad-final-content">
          <h2>
            The CAD revolution starts here.
          </h2>
          <p>
            Join the engineers and designers who are ready for AI-native design tools. 
            Be the first to experience ArchgenCAD.
          </p>
          {!submitted ? (
            <form className="acad-waitlist-form acad-waitlist-form-lg" onSubmit={handleWaitlist}>
              <input
                type="email"
                className="acad-email-input"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <button type="submit" className="acad-waitlist-btn">
                Join the Waitlist <ArrowRight size={16} />
              </button>
            </form>
          ) : (
            <div className="acad-waitlist-success">
              <Check size={20} />
              <span>You're on the list!</span>
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="acad-footer">
        <p>© {new Date().getFullYear()} Archgen · Building the future of engineering software</p>
      </footer>
    </div>
  );
}
