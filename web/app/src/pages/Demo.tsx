import { useRef, useState, useEffect, Suspense } from 'react';
import { ArrowRight, FileText, Zap, Layers, Box, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import * as THREE from 'three';
// @ts-expect-error - three.js JSM modules lack type declarations
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader';
import './Demo.css';

// ============================================
// DESIGN DATA
// ============================================
const DESIGNS = [
  {
    id: 1,
    prompt: 'design a simple turbine with 3 long blades',
    title: '3-Blade Turbine',
    category: 'Mechanical / Energy',
    generationTime: '328.6s',
    qualityScore: 92,
    modelUrl: '/final_model.stl',
    format: ['STL', 'STEP', 'OBJ', 'IGES'],
    parameters: [
      { label: 'Blades', value: '3' },
      { label: 'Type', value: 'Long' },
      { label: 'API Calls', value: '9' }
    ],
    icon: Zap,
    accentColor: '#5DA9E9',
  },
  {
    id: 2,
    prompt: 'deisgn a hostel complex , 4 building each with 4 floors , proper hostel rooms',
    title: 'Hostel Complex',
    category: 'Architecture',
    generationTime: '780.3s',
    qualityScore: 88,
    modelUrl: '/models/hostel.stl',
    format: ['STL', 'STEP', 'OBJ'],
    parameters: [
      { label: 'Buildings', value: '4' },
      { label: 'Floors', value: '4' },
      { label: 'API Calls', value: '7' },
    ],
    icon: Box,
    accentColor: '#5DA9E9',
  },
  {
    id: 3,
    prompt: 'To design a structural arc bridge that mirrors the modernist, institutional aesthetics',
    title: 'Structural Arc Bridge',
    category: 'Civil / Structural',
    generationTime: '445.1s',
    qualityScore: 94,
    modelUrl: '/models/bridge.stl',
    format: ['STL', 'STEP', 'OBJ', 'IGES'],
    parameters: [
      { label: 'Type', value: 'Arc Bridge' },
      { label: 'Aesthetic', value: 'Modernist' },
      { label: 'API Calls', value: '10' }
    ],
    icon: Layers,
    accentColor: '#5DA9E9',
  },
  {
    id: 4,
    prompt: 'Design a gear with 24 teeth and module 2',
    title: 'Spur Gear Transmission',
    category: 'Mechanical / Power Train',
    generationTime: '267.9s',
    qualityScore: 91,
    modelUrl: '/models/gear.stl',
    format: ['STL', 'STEP'],
    parameters: [
      { label: 'Teeth', value: '24' },
      { label: 'Module', value: '2' },
      { label: 'API Calls', value: '8' },
    ],
    icon: Settings,
    accentColor: '#5DA9E9',
  },
  {
    id: 5,
    prompt: 'A high-resolution, engineering-grade 3D CAD model of a massive, coastal architectural complex',
    title: 'Coastal Architectural Complex',
    category: 'Architecture',
    generationTime: '927.4s',
    qualityScore: 97,
    modelUrl: '/models/coastal.stl',
    format: ['STL', 'OBJ', 'STEP'],
    parameters: [
      { label: 'Resolution', value: 'High' },
      { label: 'Scale', value: 'Massive' },
      { label: 'API Calls', value: '8' },
    ],
    icon: Layers,
    accentColor: '#5DA9E9',
  },
  {
    id: 6,
    prompt: 'Create an L-shaped bracket with mounting holes',
    title: 'L-Shaped Structural Bracket',
    category: 'Manufacturing / Fixtures',
    generationTime: '94.3s',
    qualityScore: 86,
    modelUrl: '/models/lbracket.stl',
    format: ['STL', 'STEP', 'IGES'],
    parameters: [
      { label: 'Shape', value: 'L-Bracket' },
      { label: 'Feature', value: 'Mounting Holes' },
      { label: 'API Calls', value: '7' }
    ],
    icon: Box,
    accentColor: '#5DA9E9',
  }
];

// ============================================
// INLINE STL VIEWER MODEL
// ============================================
function STLModel({ accentColor, url }: { accentColor: string, url: string }) {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const edgesRef = useRef<THREE.LineSegments>(null);

  useEffect(() => {
    const loader = new STLLoader();
    loader.load(
      url,
      (geo: THREE.BufferGeometry) => {
        geo.computeVertexNormals();
        // Auto-scale: normalise to fit inside a 2-unit cube
        geo.computeBoundingBox();
        const box = geo.boundingBox!;
        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 2 / maxDim;
        geo.scale(scale, scale, scale);
        // Centre at origin
        geo.computeBoundingBox();
        const centre = new THREE.Vector3();
        geo.boundingBox!.getCenter(centre);
        geo.translate(-centre.x, -centre.y, -centre.z);
        setGeometry(geo);
      },
      undefined,
      (err: unknown) => console.warn('STL load error:', err),
    );
  }, []);

  // Gentle auto-rotate
  useEffect(() => {
    if (!meshRef.current) return;
    let animId: number;
    const tick = () => {
      if (meshRef.current) {
        meshRef.current.rotation.z += 0.003;
        if (edgesRef.current) edgesRef.current.rotation.z += 0.003;
      }
      animId = requestAnimationFrame(tick);
    };
    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, []);

  if (!geometry) return null;

  const edgesGeo = new THREE.EdgesGeometry(geometry, 15);

  return (
    <group>
      <mesh ref={meshRef} geometry={geometry} castShadow receiveShadow>
        <meshStandardMaterial
          color="#3a3a40"
          roughness={0.85}
          metalness={0.2}
        />
      </mesh>
      {/* Crisp edge overlay */}
      <lineSegments ref={edgesRef} geometry={edgesGeo}>
        <lineBasicMaterial
          color={accentColor}
          transparent
          opacity={0.5}
        />
      </lineSegments>
    </group>
  );
}

// ============================================
// LAZY 3D CANVAS — only mounts when visible
// ============================================
function LazyViewer({ accentColor, isVisible, url }: { accentColor: string; isVisible: boolean, url: string }) {
  if (!isVisible) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-white/10 border-t-[#5DA9E9] rounded-full animate-spin" />
      </div>
    );
  }

  return (
      <Canvas
      shadows
      dpr={[1, 1.5]}
      camera={{ position: [0, 1.2, 3.5], fov: 50 }}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1 }}
      onCreated={({ gl }) => {
        gl.setClearColor('#111318');
        const canvas = gl.domElement;
        canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); });
      }}
      style={{ background: '#111318' }}
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 10, 5]} intensity={1.4} castShadow />
      <directionalLight position={[-4, 2, -4]} intensity={0.3} color="#667eea" />

      <Suspense fallback={null}>
        <STLModel accentColor={accentColor} url={url} />
      </Suspense>

      <Grid
        args={[20, 20]}
        cellColor="#ffffff08"
        sectionColor="#ffffff05"
        sectionSize={1}
        cellSize={0.25}
        fadeDistance={8}
        position={[0, -1.4, 0]}
      />

      <OrbitControls
        enablePan={false}
        enableZoom={true}
        autoRotate={false}
        minDistance={1.5}
        maxDistance={8}
      />
    </Canvas>
  );
}

// ============================================
// SINGLE DESIGN CARD
// ============================================
function DesignCard({ design, index }: { design: typeof DESIGNS[0]; index: number }) {
  const [isVisible, setIsVisible] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const Icon = design.icon;

  useEffect(() => {
    // First card initializes immediately for fast visual hook
    if (index === 0) {
      setTimeout(() => {
        setIsVisible(true);
        setHasInitialized(true);
      }, 200);
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasInitialized) {
          setTimeout(() => {
            setIsVisible(true);
            setHasInitialized(true);
          }, index * 60);
        }
      },
      // Large positive rootMargin: pre-load canvas before user reaches it
      { threshold: 0.05, rootMargin: '400px 0px 0px 0px' },
    );

    if (cardRef.current) observer.observe(cardRef.current);
    return () => observer.disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  return (
    <div
      ref={cardRef}
      className="demo-card"
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(40px)',
        transition: `opacity 0.7s ease ${index * 0.08}s, transform 0.7s ease ${index * 0.08}s`,
      }}
    >
      {/* LEFT — Prompt & Info */}
      <div className="demo-left">
        {/* Header */}
        <div className="demo-card-header">
          <div
            className="demo-icon-badge"
            style={{ background: `${design.accentColor}15`, borderColor: `${design.accentColor}30` }}
          >
            <Icon size={18} style={{ color: design.accentColor }} />
          </div>
          <div>
            <span className="demo-category">{design.category}</span>
            <h3 className="demo-title">{design.title}</h3>
          </div>
        </div>

        {/* Prompt Block */}
        <div className="demo-prompt-block">
          <div className="demo-prompt-label">
            <FileText size={11} />
            PROMPT
          </div>
          <p className="demo-prompt-text">&ldquo;{design.prompt}&rdquo;</p>
        </div>

        {/* Parameters */}
        <div className="demo-params-grid">
          {design.parameters.map((p) => (
            <div key={p.label} className="demo-param">
              <span className="demo-param-label">{p.label}</span>
              <span className="demo-param-value" style={{ color: design.accentColor }}>{p.value}</span>
            </div>
          ))}
        </div>

        {/* Meta row */}
        <div className="demo-meta-row">
          <div className="demo-meta-item">
            <span className="demo-meta-label">Generated in</span>
            <span className="demo-meta-value">{design.generationTime}</span>
          </div>
          <div className="demo-meta-item">
            <span className="demo-meta-label">Quality</span>
            <span className="demo-meta-value">{design.qualityScore}%</span>
          </div>
          <div className="demo-meta-item demo-formats">
            {design.format.map((f) => (
              <span key={f} className="demo-format-chip">{f}</span>
            ))}
          </div>
        </div>

        {/* CTA */}
        <Link to="/studio" className="demo-cta-btn">
          Try this in Studio
          <ArrowRight size={14} />
        </Link>
      </div>

      {/* RIGHT — 3D Viewer */}
      <div className="demo-viewer-wrap">
        {/* Accent glow behind viewer */}
        <div
          className="demo-viewer-glow"
          style={{ background: `radial-gradient(circle at 50% 50%, ${design.accentColor}20 0%, transparent 70%)` }}
        />
        <div className="demo-viewer-box">
          <LazyViewer accentColor={design.accentColor} isVisible={hasInitialized} url={design.modelUrl} />
        </div>
        <div className="demo-viewer-label">
          Archgen Text-to-CAD · Drag to orbit · Scroll to zoom
        </div>
      </div>
    </div>
  );
}

// ============================================
// MAIN PAGE
// ============================================
export default function Demo() {
  return (
    <div className="demo-page">
      {/* Hero Text */}
      <div className="demo-hero">
        <div className="demo-hero-badge">
          <Zap size={12} />
          Live Showcase
        </div>
        <h1 className="demo-hero-title">
          The <span className="gradient-text">Physora</span> Design Showcase
        </h1>
        <p className="demo-hero-sub">
          Six high-fidelity designs generated by the Physora Engine. Each model is a precise, parametric B-Rep deconstructed into its fundamental engineering constraints.
        </p>
      </div>

      {/* Design Cards */}
      <main className="demo-cards-list">
        {DESIGNS.map((design, i) => (
          <DesignCard key={design.id} design={design} index={i} />
        ))}
      </main>

      {/* Bottom CTA */}
      <section className="demo-bottom-cta">
        <h2 className="demo-cta-title">Ready to generate your own?</h2>
        <p className="demo-cta-sub">Open the studio and describe what you need to build.</p>
        <Link to="/studio" className="btn-primary btn-glow flex items-center gap-2 mx-auto w-fit">
          Open Studio
          <ArrowRight size={16} />
        </Link>
      </section>

    </div>
  );
}
