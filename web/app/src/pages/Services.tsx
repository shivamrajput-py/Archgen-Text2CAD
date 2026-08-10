import { useState, useEffect, useRef } from 'react';
import {
  ArrowRight, Cog, Building2, BrainCircuit, Activity,
  Check, Zap, Terminal, Layers, Globe, ChevronRight, Sparkles,
  PenTool, Boxes, BarChart,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import './Services.css';

// ============================================
// DATA
// ============================================

// Current live product
const CURRENT_PRODUCT = {
  badge: 'Available Now',
  name: 'Archgen Text-to-CAD',
  tagline: 'The AI model that turns natural language into precision geometry.',
  description: 'Type a design intent. Archgen compiles it into parametric, editable CAD geometry - exported as STEP, STL, OBJ, or IGES files, ready for manufacturing.',
  features: [
    'Natural language to STL / STEP / OBJ / IGES in seconds',
    'Parametric, fully editable output',
    'Constraint-aware geometry compilation',
    'Web Studio + plugin ecosystem available today',
    'Multi-format export ready for CNC & 3D printing',
  ],
  specs: [
    { label: 'Inference Latency', value: '< 125s' },
    { label: 'Fidelity', value: 'High' },
    { label: 'Architecture', value: 'AI-Native' },
    { label: 'Export', value: 'STEP . STL . OBJ . IGES' },
  ],
};

// Future product suite
const PRODUCT_SUITE = [
  {
    icon: Cog,
    name: 'Archgen Mechanical',
    domain: 'Mechanical / Product Design',
    description: 'From 2D drafting to 3D parametric modelling, sheet metal, and generative engineering. AI-native from the ground up.',
    status: 'In Development',
    statusColor: '#5DA9E9',
    color: '#5DA9E9',
    features: ['Parametric solid modelling', 'Assembly & simulation', 'Sheet metal & generative design'],
  },
  {
    icon: Building2,
    name: 'Archgen BIM',
    domain: 'AEC / Regulation-Aware Architecture',
    description: 'Text-to-BIM layouts, structural design, and architectural compliance seamlessly automated with regulation-aware AI.',
    status: 'Coming Soon',
    statusColor: '#667eea',
    color: '#667eea',
    features: ['Text-to-BIM layout generation', 'Structural design automation', 'Regulation-aware compliance'],
  },
  {
    icon: BrainCircuit,
    name: 'Archgen PCB',
    domain: 'Electronics & Semiconductor (EDA)',
    description: 'Text-to-circuit design, PCB layout, and schematic capture logic with AI-native electronics synthesis.',
    status: 'Coming Soon',
    statusColor: '#48bb78',
    color: '#48bb78',
    features: ['Text-to-circuit generation', 'PCB layout automation', 'Schematic AI capture'],
  },
  {
    icon: Activity,
    name: 'Archgen CAE',
    domain: 'AI-Native Physics Validation',
    description: 'Automated simulation loops, stress & strain validation, and deep material physics connected directly to geometry.',
    status: 'Coming Soon',
    statusColor: '#ed8936',
    color: '#ed8936',
    features: ['Stress & strain simulation', 'Material physics engine', 'Automated validation loops'],
  },
];

// Capability coverage
const CAPABILITIES = [
  { icon: PenTool, label: '2D Drafting', detail: 'Precision 2D workflows' },
  { icon: Boxes, label: '3D Modelling', detail: 'Parametric solid modelling' },
  { icon: Cog, label: 'Mechanical', detail: 'Assemblies & simulation' },
  { icon: Building2, label: 'Architectural', detail: 'BIM-ready design' },
  { icon: Layers, label: 'Structural', detail: 'Load analysis & optimisation' },
  { icon: BrainCircuit, label: 'AI-Native', detail: 'Built with AI at the core' },
  { icon: Activity, label: 'Physics Validation', detail: 'Stress, strain & CAE' },
  { icon: BarChart, label: 'Material Analysis', detail: 'Cost & material estimation' },
];

// Integrations / current access points
const INTEGRATIONS = [
  {
    name: 'Archgen Web Studio',
    status: 'Live',
    description: 'Browser-based Text-to-CAD interface. No installation needed.',
    color: '#5DA9E9',
    icon: Globe,
    action: { label: 'Open Studio', href: '/studio' },
  },
  {
    name: 'ArchGen Plugin',
    status: 'Available',
    description: 'Bring Archgen directly into your CAD workflow via the ArchgenCAD workbench.',
    color: '#667eea',
    icon: Terminal,
    action: { label: 'View on GitHub', href: 'https://github.com/archgen/workbench' },
    install: 'git clone https://github.com/archgen/workbench.git ArchgenCAD',
  },
  {
    name: 'API Access',
    status: 'Beta',
    description: 'Integrate Archgen generation directly into your own tools and pipelines.',
    color: '#48bb78',
    icon: Zap,
    action: { label: 'Request Access', href: '/signin' },
  },
];

// ============================================
// COUNTER HOOK
// ============================================
function useCountUp(end: number, duration = 2000, active = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!active) return;
    let startTime: number;
    let frame: number;
    const tick = (ts: number) => {
      if (!startTime) startTime = ts;
      const p = Math.min((ts - startTime) / duration, 1);
      setCount(Math.floor(p * end));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [end, duration, active]);
  return count;
}

// ============================================
// MAIN COMPONENT
// ============================================
export default function Services() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [statsVisible, setStatsVisible] = useState(false);
  const statsRef = useRef<HTMLDivElement>(null);
  const [sectionsVisible, setSectionsVisible] = useState<Record<string, boolean>>({});

  // Intersection observer for multiple sections
  useEffect(() => {
    const sections = document.querySelectorAll('[data-section]');
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setSectionsVisible(prev => ({ ...prev, [entry.target.getAttribute('data-section')!]: true }));
      }
    }, { threshold: 0.08 });
    sections.forEach(s => io.observe(s));
    if (statsRef.current) {
      const statIo = new IntersectionObserver(([e]) => { if (e.isIntersecting) setStatsVisible(true); }, { threshold: 0.3 });
      statIo.observe(statsRef.current);
    }
    return () => io.disconnect();
  }, []);

  const stat1 = useCountUp(10, 1800, statsVisible);
  const stat2 = useCountUp(4, 1800, statsVisible);
  const stat3 = useCountUp(100, 1800, statsVisible);

  const handleWaitlist = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) setSubmitted(true);
  };

  return (
    <div className="svc-page">
      {/* BACKGROUND */}
      <div className="svc-bg-grid opacity-20" />



      {/* ===================== HERO ===================== */}
      <section className="svc-hero">
        <div className="svc-hero-label">
          <Sparkles size={11} />
          Services & Products
        </div>
        <h1 className="svc-hero-title">
          One Vision.<br />
          <span className="gradient-text">Many Platforms.</span>
        </h1>
        <p className="svc-hero-sub">
          Archgen is building the AI-native design stack — not plugins on legacy tools,
          but entirely new platforms engineered from the ground up with intelligence at the core.
        </p>
        <div className="svc-hero-actions">
          <Link to="/studio" className="btn-primary btn-glow flex items-center gap-2">
            Try for Free <ArrowRight size={15} />
          </Link>
          <Link to="/demo" className="btn-secondary flex items-center gap-2">
            See Demo Designs
          </Link>
        </div>

        {/* Scroll hint */}
        <div className="svc-scroll-hint">
          <div className="svc-scroll-dot" />
        </div>
      </section>

      {/* ===================== STATS STRIP ===================== */}
      <div className="svc-stats-strip" ref={statsRef} data-section="stats">
        <div className="svc-stat">
          <span className="svc-stat-num">{stat1}x</span>
          <span className="svc-stat-label">Faster Design Iterations</span>
        </div>
        <div className="svc-stat-divider" />
        <div className="svc-stat">
          <span className="svc-stat-num">{stat2}</span>
          <span className="svc-stat-label">AI-Native Platforms Planned</span>
        </div>
        <div className="svc-stat-divider" />
        <div className="svc-stat">
          <span className="svc-stat-num">{stat3}%</span>
          <span className="svc-stat-label">AI-Native Architecture</span>
        </div>
        <div className="svc-stat-divider" />
        <div className="svc-stat">
          <span className="svc-stat-num">50+</span>
          <span className="svc-stat-label">Engineers Trusting Archgen</span>
        </div>
      </div>

      {/* ===================== CURRENT PRODUCT — FEATURED ===================== */}
      <section
        className="svc-section"
        data-section="current"
        style={{
          opacity: sectionsVisible['current'] ? 1 : 0,
          transform: sectionsVisible['current'] ? 'none' : 'translateY(32px)',
          transition: 'opacity 0.7s ease, transform 0.7s ease',
        }}
      >
        <div className="svc-section-inner">
          <div className="svc-eyebrow">
            <div className="svc-eyebrow-dot" style={{ background: '#48bb78' }} />
            <span style={{ color: '#48bb78' }}>Available Now</span>
          </div>
          <div className="svc-current-grid">
            {/* Left */}
            <div className="svc-current-left">
              <div className="svc-featured-badge">FLAGSHIP</div>
              <h2 className="svc-section-title">{CURRENT_PRODUCT.name}</h2>
              <p className="svc-current-tagline">{CURRENT_PRODUCT.tagline}</p>
              <p className="svc-current-desc">{CURRENT_PRODUCT.description}</p>

              <ul className="svc-check-list">
                {CURRENT_PRODUCT.features.map(f => (
                  <li key={f}>
                    <span className="svc-check-icon"><Check size={12} /></span>
                    {f}
                  </li>
                ))}
              </ul>

              <div className="svc-current-actions">
                <Link to="/studio" className="btn-primary btn-glow flex items-center gap-2">
                  Open Studio <ArrowRight size={14} />
                </Link>
                <Link to="/demo" className="btn-secondary flex items-center gap-2">
                  See Output Demos
                </Link>
              </div>
            </div>

            {/* Right — Specs + Terminal */}
            <div className="svc-current-right">
              {/* Tech specs */}
              <div className="svc-specs-grid">
                {CURRENT_PRODUCT.specs.map(s => (
                  <div key={s.label} className="svc-spec-card">
                    <span className="svc-spec-label">{s.label}</span>
                    <span className="svc-spec-value">{s.value}</span>
                  </div>
                ))}
              </div>

              {/* Terminal prompt demo */}
              <div className="svc-terminal">
                <div className="svc-terminal-bar">
                  <div className="svc-terminal-dots">
                    <span /><span /><span />
                  </div>
                  <span className="svc-terminal-title">archgen.ai/studio</span>
                  <span className="svc-terminal-status">LIVE</span>
                </div>
                <div className="svc-terminal-body">
                  <p><span className="t-accent">{'>'}</span> Design a 3-blade wind turbine rotor</p>
                  <p className="t-muted">  optimised for 15 m/s with NACA 4412 aerofoil,</p>
                  <p className="t-muted">  2.4 m blade span, hub mounting flange.</p>
                  <br />
                  <p><span className="t-green">✓</span> Architecture: Parametric</p>
                  <p><span className="t-green">✓</span> Constraints: Applied · Quality: 87%</p>
                  <p><span className="t-green">✓</span> Export: STEP | STL | OBJ | IGES</p>
                  <div className="svc-cursor-row">
                    <span className="t-accent">{'>'}</span>
                    <div className="svc-cursor" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================== FUTURE PRODUCT SUITE ===================== */}
      <section
        className="svc-section svc-section-alt"
        data-section="suite"
        style={{
          opacity: sectionsVisible['suite'] ? 1 : 0,
          transform: sectionsVisible['suite'] ? 'none' : 'translateY(32px)',
          transition: 'opacity 0.7s ease, transform 0.7s ease',
        }}
      >
        <div className="svc-section-inner">
          <div className="svc-eyebrow">
            <div className="svc-eyebrow-dot" style={{ background: '#667eea' }} />
            <span style={{ color: '#667eea' }}>The Roadmap</span>
          </div>
          <div className="svc-section-head">
            <h2 className="svc-section-title">
              AI-Native Platforms <span className="gradient-text">Coming Next</span>
            </h2>
            <p className="svc-section-desc">
              We're not adding AI features to legacy software. We're building entirely new platforms — 
              covering the full spectrum of engineering design.
            </p>
          </div>

          <div className="svc-suite-grid">
            {PRODUCT_SUITE.map((product, idx) => {
              const Icon = product.icon;
              return (
                <div
                  key={product.name}
                  className="svc-suite-card"
                  style={{
                    borderColor: `${product.color}20`,
                    opacity: sectionsVisible['suite'] ? 1 : 0,
                    transform: sectionsVisible['suite'] ? 'translateY(0)' : 'translateY(24px)',
                    transition: `opacity 0.6s ease ${idx * 0.1}s, transform 0.6s ease ${idx * 0.1}s`,
                  }}
                >
                  {/* Status */}
                  <div
                    className="svc-suite-status"
                    style={{ color: product.statusColor, background: `${product.statusColor}12`, borderColor: `${product.statusColor}25` }}
                  >
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: product.statusColor }} />
                    {product.status}
                  </div>

                  {/* Icon + Name */}
                  <div className="svc-suite-icon-row">
                    <div
                      className="svc-suite-icon"
                      style={{ background: `${product.color}12`, borderColor: `${product.color}25` }}
                    >
                      <Icon size={22} style={{ color: product.color }} />
                    </div>
                  </div>
                  <p className="svc-suite-domain">{product.domain}</p>
                  <h3 className="svc-suite-name">{product.name}</h3>
                  <p className="svc-suite-desc">{product.description}</p>

                  {/* Feature list */}
                  <ul className="svc-suite-features">
                    {product.features.map(f => (
                      <li key={f}>
                        <span style={{ color: product.color, marginRight: '6px' }}>—</span>
                        {f}
                      </li>
                    ))}
                  </ul>

                  {/* Bottom hover glow */}
                  <div
                    className="svc-suite-glow"
                    style={{ background: `linear-gradient(90deg, transparent, ${product.color}25, transparent)` }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===================== CAPABILITY COVERAGE ===================== */}
      <section
        className="svc-section"
        data-section="capabilities"
        style={{
          opacity: sectionsVisible['capabilities'] ? 1 : 0,
          transform: sectionsVisible['capabilities'] ? 'none' : 'translateY(32px)',
          transition: 'opacity 0.7s ease, transform 0.7s ease',
        }}
      >
        <div className="svc-section-inner">
          <div className="svc-eyebrow">
            <div className="svc-eyebrow-dot" style={{ background: '#5DA9E9' }} />
            <span style={{ color: '#5DA9E9' }}>Coverage</span>
          </div>
          <div className="svc-section-head">
            <h2 className="svc-section-title">
              Every Discipline. <span className="gradient-text">Every Scale.</span>
            </h2>
            <p className="svc-section-desc">
              From small mechanical parts to massive structural projects — Archgen covers the full engineering design spectrum.
            </p>
          </div>

          <div className="svc-cap-grid">
            {CAPABILITIES.map((cap, idx) => {
              const Icon = cap.icon;
              return (
                <div
                  key={cap.label}
                  className="svc-cap-card"
                  style={{
                    opacity: sectionsVisible['capabilities'] ? 1 : 0,
                    transform: sectionsVisible['capabilities'] ? 'translateY(0)' : 'translateY(20px)',
                    transition: `opacity 0.5s ease ${idx * 0.07}s, transform 0.5s ease ${idx * 0.07}s`,
                  }}
                >
                  <div className="svc-cap-icon-wrap">
                    <Icon size={20} className="text-[#5DA9E9]" />
                  </div>
                  <h4 className="svc-cap-label">{cap.label}</h4>
                  <p className="svc-cap-detail">{cap.detail}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===================== ACCESS / INTEGRATIONS ===================== */}
      <section
        className="svc-section svc-section-alt"
        data-section="integrations"
        style={{
          opacity: sectionsVisible['integrations'] ? 1 : 0,
          transform: sectionsVisible['integrations'] ? 'none' : 'translateY(32px)',
          transition: 'opacity 0.7s ease, transform 0.7s ease',
        }}
      >
        <div className="svc-section-inner">
          <div className="svc-eyebrow">
            <div className="svc-eyebrow-dot" style={{ background: '#48bb78' }} />
            <span style={{ color: '#48bb78' }}>Access</span>
          </div>
          <div className="svc-section-head">
            <h2 className="svc-section-title">
              How to Access <span className="gradient-text">Archgen</span>
            </h2>
            <p className="svc-section-desc">
              Three ways to start generating precision geometry today.
            </p>
          </div>

          <div className="svc-integrations-grid">
            {INTEGRATIONS.map((intg, idx) => {
              const Icon = intg.icon;
              const isExternal = intg.action.href.startsWith('http');
              return (
                <div
                  key={intg.name}
                  className="svc-intg-card"
                  style={{
                    borderColor: `${intg.color}20`,
                    opacity: sectionsVisible['integrations'] ? 1 : 0,
                    transform: sectionsVisible['integrations'] ? 'translateY(0)' : 'translateY(24px)',
                    transition: `opacity 0.6s ease ${idx * 0.12}s, transform 0.6s ease ${idx * 0.12}s`,
                  }}
                >
                  <div className="svc-intg-top">
                    <div
                      className="svc-intg-icon"
                      style={{ background: `${intg.color}12`, borderColor: `${intg.color}25` }}
                    >
                      <Icon size={20} style={{ color: intg.color }} />
                    </div>
                    <div
                      className="svc-intg-status"
                      style={{ color: intg.color, background: `${intg.color}10`, borderColor: `${intg.color}25` }}
                    >
                      {intg.status}
                    </div>
                  </div>
                  <h3 className="svc-intg-name">{intg.name}</h3>
                  <p className="svc-intg-desc">{intg.description}</p>

                  {intg.install && (
                    <div className="svc-intg-install">
                      <span className="t-accent">$</span> {intg.install}
                    </div>
                  )}

                  <div className="svc-intg-footer">
                    {isExternal ? (
                      <a
                        href={intg.action.href}
                        target="_blank"
                        rel="noreferrer"
                        className="svc-intg-btn"
                        style={{ color: intg.color, borderColor: `${intg.color}30` }}
                      >
                        {intg.action.label} <ChevronRight size={13} />
                      </a>
                    ) : (
                      <Link
                        to={intg.action.href}
                        className="svc-intg-btn"
                        style={{ color: intg.color, borderColor: `${intg.color}30` }}
                      >
                        {intg.action.label} <ChevronRight size={13} />
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===================== VISION / WHY ARCHGEN ===================== */}
      <section
        className="svc-section"
        data-section="vision"
        style={{
          opacity: sectionsVisible['vision'] ? 1 : 0,
          transition: 'opacity 0.7s ease',
        }}
      >
        <div className="svc-section-inner svc-vision-inner">
          <div className="svc-vision-left">
            <div className="svc-eyebrow svc-eyebrow-left">
              <div className="svc-eyebrow-dot" style={{ background: '#ed8936' }} />
              <span style={{ color: '#ed8936' }}>Philosophy</span>
            </div>
            <h2 className="svc-section-title">
              Why AI-Native<br />
              <span className="gradient-text">Matters</span>
            </h2>
            <p className="svc-section-desc svc-vision-desc">
              Legacy CAD tools were built for mouse-and-click workflows. Archgen is built for intent. Just like Cursor transformed software development, Archgen transforms engineering design.
            </p>
            <p className="svc-section-desc svc-vision-desc mt-4">
              We don't add AI as a feature to old software. We start from scratch with intelligence at the foundation — parametric compilers, constraint reasoning, semantic intent extraction.
            </p>
          </div>
          <div className="svc-vision-right">
            {[
              { label: 'Legacy CAD', desc: 'Click, constrain, repeat. Slow iteration. Manual geometry.', neg: true },
              { label: 'AI-augmented CAD', desc: 'Copilot features bolted onto existing tools. Still fundamentally manual.', neg: true },
              { label: 'Archgen — AI-Native', desc: 'Describe intent. Compile geometry. Iterate in seconds. Built for this.', neg: false },
            ].map((item) => (
              <div
                key={item.label}
                className={`svc-compare-row ${item.neg ? 'svc-compare-neg' : 'svc-compare-pos'}`}
              >
                <div className="svc-compare-dot">
                  {item.neg ? <span className="text-[#4a5568]">✕</span> : <Check size={13} className="text-[#48bb78]" />}
                </div>
                <div>
                  <p className={`svc-compare-title ${item.neg ? '' : 'text-[#F5F7FA]'}`}>{item.label}</p>
                  <p className="svc-compare-desc">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

    <section className="svc-cta-section relative overflow-hidden bg-[#0D1117] border-t border-white/5 py-32 z-20">
        <div className="svc-cta-inner">
          <div className="svc-hero-label">
            <Sparkles size={11} />
            Early Access
          </div>
          <h2 className="svc-cta-title">
            The Engineering Revolution<br />Starts Here.
          </h2>
          <p className="svc-cta-desc">
            Join the engineers and designers shaping the future of AI-native design tools.
          </p>

          {!submitted ? (
            <form className="svc-waitlist-form" onSubmit={handleWaitlist}>
              <input
                type="email"
                className="svc-email-input"
                placeholder="your@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
              <button type="submit" className="svc-waitlist-btn">
                Join Waitlist <ArrowRight size={15} />
              </button>
            </form>
          ) : (
            <div className="svc-success">
              <div className="svc-success-icon"><Check size={16} /></div>
              <span>You're on the list! We'll be in touch.</span>
            </div>
          )}

          <p className="svc-cta-hint">No spam. Early access to all Archgen platforms.</p>
        </div>
      </section>


    </div>
  );
}
