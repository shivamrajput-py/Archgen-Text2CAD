import { ArrowRight, Play, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Center, Environment } from '@react-three/drei';
import { useEffect, useState } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';

function HeroModel() {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);

  useEffect(() => {
    const loader = new STLLoader();
    loader.load(
      '/final_model.stl', // Using the STL available in public folder
      (geo) => {
        geo.computeBoundingBox();
        geo.center();
        geo.computeVertexNormals();
        
        // Scale down slightly to fit nicely in the view
        const boundingBox = geo.boundingBox!;
        const size = new THREE.Vector3();
        boundingBox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const targetSize = 4.5;
        const normalizedScale = maxDim > 0 ? targetSize / maxDim : 1;
        geo.scale(normalizedScale, normalizedScale, normalizedScale);
        
        setGeometry(geo);
      },
      undefined,
      (err) => console.error('Error loading Hero STL:', err)
    );
  }, []);

  if (!geometry) return null;

  return (
    <Center>
      <group rotation={[Math.PI / 6, Math.PI / 4, 0]}>
        <mesh geometry={geometry} castShadow receiveShadow>
          <meshStandardMaterial
            color="#5c6878"
            metalness={0.5}
            roughness={0.6}
            envMapIntensity={1.0}
            side={THREE.DoubleSide}
          />
        </mesh>
        <lineSegments>
          <edgesGeometry args={[geometry, 25]} />
          <lineBasicMaterial color="#aabdd4" opacity={0.3} transparent />
        </lineSegments>
      </group>
    </Center>
  );
}

export function Hero() {
  return (
    <section className="relative w-full overflow-hidden bg-[#0D1117] pt-24 pb-16 min-h-[90vh] flex items-center">
      {/* Minimalist Grid Background */}
      <div className="absolute inset-0 blueprint-grid opacity-30" />
      
      <div className="absolute inset-0 bg-gradient-to-b from-[#0D1117] via-transparent to-[#0D1117] opacity-90" />
      <div className="absolute inset-0 bg-gradient-to-r from-[#0D1117] via-[#0D1117]/90 to-transparent" />

      {/* Subtle Glow - Reduced for minimal aesthetic */}
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-[#5DA9E9]/5 rounded-full blur-[120px] pointer-events-none" />

      <div className="relative z-10 w-full">
        <div className="w-full px-6 lg:px-12 xl:px-16">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-12 lg:gap-8">
            
            {/* Left Content */}
            <div className="w-full lg:w-[50%] xl:w-[45%] space-y-8 z-20">
              <div className="animate-fade-up inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                <Sparkles size={14} className="text-[#5DA9E9]" />
                <span className="font-mono text-[11px] uppercase tracking-widest text-[#5DA9E9]">State of the art Text to CAD model</span>
              </div>

              <h1 className="heading-serif text-5xl sm:text-6xl lg:text-7xl xl:text-[80px] text-[#F5F7FA] leading-[1.05] animate-fade-up" style={{ animationDelay: '0.1s' }}>
                India's First <span className="gradient-text">Generative AI</span>
                <br />
                for Physical Products.
              </h1>

              <p className="text-[#AAB4C3] text-lg lg:text-xl max-w-[480px] leading-relaxed animate-fade-up" style={{ animationDelay: '0.2s' }}>
                Powered by the <strong className="text-white">Physora Engine</strong>. Archgen translates natural language into precision, manufacturing-ready geometry with real-time physics validation.
              </p>

              <div className="flex flex-wrap gap-4 pt-2 animate-fade-up" style={{ animationDelay: '0.3s' }}>
                <Link to="/signin" className="btn-primary btn-glow flex items-center gap-2">
                  Start Structuring
                  <ArrowRight className="w-4 h-4" strokeWidth={2} />
                </Link>
                <Link to="/demo" className="btn-secondary flex items-center gap-2 group">
                  <Play className="w-4 h-4 group-hover:scale-110 transition-transform" strokeWidth={2} />
                  View Demo
                </Link>
              </div>

              {/* Trust Indicators */}
              <div className="flex items-center gap-6 pt-4 animate-fade-up" style={{ animationDelay: '0.4s' }}>
                <div className="flex -space-x-2">
                  {[...Array(4)].map((_, i) => (
                    <div
                      key={i}
                      className="w-8 h-8 rounded-full bg-gradient-to-br from-[#5DA9E9] to-[#667eea] border-2 border-[#0D1117]"
                      style={{ opacity: 1 - i * 0.2 }}
                    />
                  ))}
                </div>
                <span className="text-sm text-[#6E7A8A]">
                  Trusted by <span className="text-[#AAB4C3]">50+</span> engineers
                </span>
              </div>
            </div>

            {/* Right Content - Interactive 3D Model */}
            <div className="w-full lg:w-[50%] xl:w-[55%] relative h-[500px] lg:h-[600px] animate-fade-up z-10" style={{ animationDelay: '0.5s' }}>
              <div className="absolute inset-0 rounded-2xl overflow-hidden bg-gradient-to-br from-[#141B24]/40 to-[#0D1117]/40 border border-[#5DA9E9]/10 backdrop-blur-sm">
                
                {/* 3D Canvas */}
                <Canvas
                  camera={{ position: [8, 6, 8], fov: 45 }}
                  gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.2 }}
                >
                  <ambientLight intensity={1.5} />
                  <directionalLight position={[10, 10, 5]} intensity={2} />
                  <directionalLight position={[-10, -10, -5]} intensity={0.5} color="#5DA9E9" />
                  
                  <HeroModel />
                  
                  <OrbitControls 
                    enableZoom={false} 
                    enablePan={false}
                    autoRotate={true}
                    autoRotateSpeed={1.5}
                    minPolarAngle={Math.PI / 3}
                    maxPolarAngle={Math.PI / 1.5}
                  />
                  <Environment preset="city" />
                </Canvas>
                
                {/* Minimal Overlay UI */}
                <div className="absolute bottom-4 left-4 right-4 flex justify-between items-center pointer-events-none">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-[#5DA9E9] animate-pulse" />
                    <span className="text-[10px] uppercase tracking-widest text-[#5DA9E9] font-mono">Interactive Model</span>
                  </div>
                  <span className="text-[10px] text-white/40 font-mono tracking-widest hidden sm:inline-block">
                    PRODUCED BY ARCHGEN AI
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative Line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </section>
  );
}
