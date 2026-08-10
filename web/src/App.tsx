import React, { useState, useRef, useCallback } from 'react';
import { 
  Settings, 
  Download, 
  User, 
  RotateCcw, 
  Box, 
  Maximize2, 
  ChevronDown,
  ChevronUp,
  Send,
  Layers,
  Ruler,
  Grid3X3
} from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import * as THREE from 'three';

// ============================================
// TYPES
// ============================================
interface Message {
  id: string;
  type: 'user' | 'system';
  content: string;
  timestamp: Date;
}

interface TowerParams {
  floors: number;
  width: number;
  height: number;
  rotation: number;
}

// ============================================
// THREE.JS COMPONENTS
// ============================================

interface TowerProps {
  params: TowerParams;
  wireframe: boolean;
}

function ParametricTower({ params, wireframe }: TowerProps) {
  const groupRef = useRef<THREE.Group>(null);
  const { floors, width, height } = params;
  
  // Generate tower geometry
  const towerElements = React.useMemo(() => {
    const elements: React.ReactElement[] = [];
    const floorHeight = height / floors;
    const coreWidth = width * 0.3;
    
    // Central core
    elements.push(
      <mesh key="core" position={[0, height / 2, 0]}>
        <boxGeometry args={[coreWidth, height, coreWidth]} />
        <meshStandardMaterial 
          color="#e8e8e8" 
          roughness={0.4}
          metalness={0.1}
          wireframe={wireframe}
        />
      </mesh>
    );
    
    // Floor slabs
    for (let i = 0; i < floors; i++) {
      const y = i * floorHeight + floorHeight / 2;
      const slabWidth = width * (1 - (i / floors) * 0.15); // Slight taper
      
      elements.push(
        <mesh key={`floor-${i}`} position={[0, y, 0]}>
          <boxGeometry args={[slabWidth, floorHeight * 0.15, slabWidth]} />
          <meshStandardMaterial 
            color="#f5f5f5" 
            roughness={0.35}
            metalness={0.05}
            wireframe={wireframe}
          />
        </mesh>
      );
      
      // Corner columns
      const offset = slabWidth * 0.4;
      const corners = [
        [offset, offset],
        [-offset, offset],
        [offset, -offset],
        [-offset, -offset]
      ];
      
      corners.forEach((corner, j) => {
        elements.push(
          <mesh key={`column-${i}-${j}`} position={[corner[0], y, corner[1]]}>
            <boxGeometry args={[width * 0.04, floorHeight * 0.9, width * 0.04]} />
            <meshStandardMaterial 
              color="#d0d0d0" 
              roughness={0.5}
              metalness={0.2}
              wireframe={wireframe}
            />
          </mesh>
        );
      });
    }
    
    // Top crown
    elements.push(
      <mesh key="crown" position={[0, height + 2, 0]}>
        <boxGeometry args={[width * 0.5, 4, width * 0.5]} />
        <meshStandardMaterial 
          color="#c0c0c0" 
          roughness={0.45}
          metalness={0.15}
          wireframe={wireframe}
        />
      </mesh>
    );
    
    return elements;
  }, [floors, width, height, wireframe]);
  
  React.useEffect(() => {
    const animate = () => {
      if (groupRef.current) {
        groupRef.current.rotation.y = params.rotation * (Math.PI / 180) + Date.now() * 0.00005;
      }
      requestAnimationFrame(animate);
    };
    const animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, [params.rotation]);
  
  return (
    <group ref={groupRef}>
      {towerElements}
    </group>
  );
}

function Scene({ params, wireframe }: TowerProps) {
  return (
    <>
      {/* Ambient light */}
      <ambientLight intensity={0.4} />
      
      {/* Directional light */}
      <directionalLight 
        position={[10, 20, 10]} 
        intensity={0.8}
        castShadow
        shadow-mapSize={[1024, 1024]}
      />
      
      {/* Fill light */}
      <directionalLight 
        position={[-10, 10, -10]} 
        intensity={0.3}
      />
      
      {/* Fog for depth */}
      <fog attach="fog" args={['#0D1117', 50, 200]} />
      
      {/* Grid helper */}
      <Grid
        position={[0, 0, 0]}
        args={[100, 100]}
        cellSize={5}
        cellThickness={0.5}
        cellColor="rgba(93, 169, 233, 0.15)"
        sectionSize={25}
        sectionThickness={1}
        sectionColor="rgba(93, 169, 233, 0.25)"
        fadeDistance={150}
        fadeStrength={1}
        infiniteGrid
      />
      
      {/* Parametric Tower */}
      <ParametricTower params={params} wireframe={wireframe} />
      
      {/* Orbit controls */}
      <OrbitControls 
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={20}
        maxDistance={150}
        maxPolarAngle={Math.PI / 2 - 0.05}
      />
    </>
  );
}

// ============================================
// UI COMPONENTS
// ============================================

function Header() {
  const [projectName, setProjectName] = useState('Untitled Tower');
  const [isEditing, setIsEditing] = useState(false);
  
  return (
    <header className="fixed top-0 left-0 right-0 h-16 z-50 bg-[#0D1117]/90 backdrop-blur-sm hairline-b">
      <div className="h-full px-6 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#5DA9E9]/10 flex items-center justify-center">
            <Grid3X3 className="w-4 h-4 text-[#5DA9E9]" />
          </div>
          <span className="font-heading font-semibold text-[#F5F7FA] tracking-tight">
            ARCHGEN <span className="text-[#AAB4C3] font-normal">Studio</span>
          </span>
        </div>
        
        {/* Project Name */}
        <div className="flex-1 flex justify-center">
          {isEditing ? (
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              onBlur={() => setIsEditing(false)}
              onKeyDown={(e) => e.key === 'Enter' && setIsEditing(false)}
              className="bg-transparent text-center text-[#F5F7FA] font-medium border-b border-[#5DA9E9] outline-none px-2 py-1"
              autoFocus
            />
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="text-[#AAB4C3] hover:text-[#F5F7FA] transition-colors font-mono text-sm tracking-wide"
            >
              {projectName}
            </button>
          )}
        </div>
        
        {/* Actions */}
        <div className="flex items-center gap-2">
          <button className="p-2 rounded-lg hover:bg-white/5 transition-colors text-[#AAB4C3] hover:text-[#F5F7FA]">
            <Settings className="w-5 h-5" />
          </button>
          <button className="p-2 rounded-lg hover:bg-white/5 transition-colors text-[#AAB4C3] hover:text-[#F5F7FA]">
            <Download className="w-5 h-5" />
          </button>
          <button className="ml-2 w-8 h-8 rounded-full bg-gradient-to-br from-[#5DA9E9]/20 to-[#5DA9E9]/5 border border-[#5DA9E9]/30 flex items-center justify-center">
            <User className="w-4 h-4 text-[#5DA9E9]" />
          </button>
        </div>
      </div>
    </header>
  );
}

interface PromptPanelProps {
  onGenerate: (prompt: string) => void;
  isGenerating: boolean;
}

function PromptPanel({ onGenerate, isGenerating }: PromptPanelProps) {
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'system',
      content: 'Welcome to Archgen Studio. Describe a structural system and I will generate parametric geometry with engineering logic.',
      timestamp: new Date()
    }
  ]);
  
  const handleGenerate = () => {
    if (!prompt.trim() || isGenerating) return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: prompt,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    onGenerate(prompt);
    setPrompt('');
  };
  
  return (
    <div className="h-full flex flex-col">
      {/* Prompt Input Area */}
      <div className="p-5 border-b border-white/5">
        <div className="font-mono text-xs text-[#5DA9E9] mb-3 tracking-wider uppercase">
          Prompt
        </div>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe your structural system..."
          className="w-full h-28 text-sm resize-none"
          disabled={isGenerating}
        />
        <button
          onClick={handleGenerate}
          disabled={!prompt.trim() || isGenerating}
          className="btn-primary w-full mt-3 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <>
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 bg-current rounded-full loading-dot" />
                <div className="w-1.5 h-1.5 bg-current rounded-full loading-dot" />
                <div className="w-1.5 h-1.5 bg-current rounded-full loading-dot" />
              </div>
              <span>Generating...</span>
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              <span>Generate</span>
            </>
          )}
        </button>
      </div>
      
      {/* Chat History */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        <div className="font-mono text-xs text-[#5DA9E9] mb-3 tracking-wider uppercase">
          History
        </div>
        {messages.map((message) => (
          <div
            key={message.id}
            className={`${
              message.type === 'user' ? 'message-user ml-8' : 'message-system mr-8'
            } rounded-lg p-3`}
          >
            <div className="text-xs text-[#AAB4C3] mb-1 font-mono">
              {message.type === 'user' ? 'You' : 'Archgen'} · {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
            <div className="text-sm text-[#F5F7FA] leading-relaxed">
              {message.content}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface ParameterControlsProps {
  params: TowerParams;
  onParamsChange: (params: TowerParams) => void;
}

function ParameterControls({ params, onParamsChange }: ParameterControlsProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const updateParam = (key: keyof TowerParams, value: number) => {
    onParamsChange({ ...params, [key]: value });
  };
  
  return (
    <div className="border-t border-white/5">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-5 py-3 flex items-center justify-between text-[#AAB4C3] hover:text-[#F5F7FA] transition-colors"
      >
        <span className="font-mono text-xs tracking-wider uppercase">Parameters</span>
        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
      </button>
      
      {isExpanded && (
        <div className="px-5 pb-5 space-y-4">
          {/* Floors */}
          <div>
            <div className="flex justify-between mb-2">
              <span className="text-xs text-[#AAB4C3]">Floors</span>
              <span className="text-xs font-mono text-[#5DA9E9]">{params.floors}</span>
            </div>
            <input
              type="range"
              min="4"
              max="40"
              value={params.floors}
              onChange={(e) => updateParam('floors', parseInt(e.target.value))}
            />
          </div>
          
          {/* Width */}
          <div>
            <div className="flex justify-between mb-2">
              <span className="text-xs text-[#AAB4C3]">Width (m)</span>
              <span className="text-xs font-mono text-[#5DA9E9]">{params.width}</span>
            </div>
            <input
              type="range"
              min="15"
              max="80"
              value={params.width}
              onChange={(e) => updateParam('width', parseInt(e.target.value))}
            />
          </div>
          
          {/* Height */}
          <div>
            <div className="flex justify-between mb-2">
              <span className="text-xs text-[#AAB4C3]">Height (m)</span>
              <span className="text-xs font-mono text-[#5DA9E9]">{params.height}</span>
            </div>
            <input
              type="range"
              min="30"
              max="300"
              value={params.height}
              onChange={(e) => updateParam('height', parseInt(e.target.value))}
            />
          </div>
          
          {/* Rotation */}
          <div>
            <div className="flex justify-between mb-2">
              <span className="text-xs text-[#AAB4C3]">Rotation (°)</span>
              <span className="text-xs font-mono text-[#5DA9E9]">{params.rotation}</span>
            </div>
            <input
              type="range"
              min="0"
              max="360"
              value={params.rotation}
              onChange={(e) => updateParam('rotation', parseInt(e.target.value))}
            />
          </div>
        </div>
      )}
    </div>
  );
}

interface ViewportOverlayProps {
  is3D: boolean;
  onToggle3D: () => void;
  wireframe: boolean;
  onToggleWireframe: () => void;
  onResetCamera: () => void;
  params: TowerParams;
}

function ViewportOverlay({ 
  is3D, 
  onToggle3D, 
  wireframe, 
  onToggleWireframe, 
  onResetCamera,
  params 
}: ViewportOverlayProps) {
  return (
    <>
      {/* Top Left - 3D/2D Toggle */}
      <div className="absolute top-4 left-4 flex bg-black/40 rounded-lg p-1 backdrop-blur-sm">
        <button
          onClick={onToggle3D}
          className={`toggle-btn ${is3D ? 'active' : ''}`}
        >
          3D
        </button>
        <button
          onClick={onToggle3D}
          className={`toggle-btn ${!is3D ? 'active' : ''}`}
        >
          2D
        </button>
      </div>
      
      {/* Top Right - View Controls */}
      <div className="absolute top-4 right-4 flex gap-2">
        <button
          onClick={onResetCamera}
          className="p-2 rounded-lg bg-black/40 backdrop-blur-sm text-[#AAB4C3] hover:text-[#F5F7FA] hover:bg-black/60 transition-all"
          title="Reset Camera"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        <button
          onClick={onToggleWireframe}
          className={`p-2 rounded-lg backdrop-blur-sm transition-all ${
            wireframe 
              ? 'bg-[#5DA9E9]/20 text-[#5DA9E9]' 
              : 'bg-black/40 text-[#AAB4C3] hover:text-[#F5F7FA] hover:bg-black/60'
          }`}
          title="Toggle Wireframe"
        >
          <Box className="w-4 h-4" />
        </button>
      </div>
      
      {/* Bottom - Metadata Bar */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-6 px-6 py-3 bg-black/60 backdrop-blur-md rounded-lg border border-white/5">
        <div className="flex items-center gap-2">
          <Ruler className="w-4 h-4 text-[#5DA9E9]" />
          <span className="text-xs text-[#AAB4C3]">Height:</span>
          <span className="text-sm font-mono text-[#F5F7FA]">{params.height}m</span>
        </div>
        <div className="w-px h-4 bg-white/10" />
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#5DA9E9]" />
          <span className="text-xs text-[#AAB4C3]">Floors:</span>
          <span className="text-sm font-mono text-[#F5F7FA]">{params.floors}</span>
        </div>
        <div className="w-px h-4 bg-white/10" />
        <div className="flex items-center gap-2">
          <Maximize2 className="w-4 h-4 text-[#5DA9E9]" />
          <span className="text-xs text-[#AAB4C3]">Width:</span>
          <span className="text-sm font-mono text-[#F5F7FA]">{params.width}m</span>
        </div>
      </div>
      
      {/* Bottom Right - Action Buttons */}
      <div className="absolute bottom-4 right-4 flex gap-2">
        <button className="btn-secondary text-xs py-2 px-4">
          Simplify
        </button>
        <button className="btn-primary text-xs py-2 px-4">
          Adjust Details
        </button>
      </div>
    </>
  );
}

// ============================================
// MAIN APP COMPONENT
// ============================================

function App() {
  const [isGenerating, setIsGenerating] = useState(false);
  const [is3D, setIs3D] = useState(true);
  const [wireframe, setWireframe] = useState(false);
  const [params, setParams] = useState<TowerParams>({
    floors: 12,
    width: 30,
    height: 120,
    rotation: 0
  });
  
  const handleGenerate = useCallback((prompt: string) => {
    setIsGenerating(true);
    
    // Simulate generation delay
    setTimeout(() => {
      // Update params based on prompt (simulated)
      const newParams = { ...params };
      
      if (prompt.toLowerCase().includes('tall')) {
        newParams.height = Math.min(300, params.height + 40);
        newParams.floors = Math.min(40, params.floors + 5);
      } else if (prompt.toLowerCase().includes('wide')) {
        newParams.width = Math.min(80, params.width + 15);
      } else if (prompt.toLowerCase().includes('compact')) {
        newParams.width = Math.max(15, params.width - 10);
        newParams.height = Math.max(30, params.height - 30);
      }
      
      setParams(newParams);
      setIsGenerating(false);
    }, 2000);
  }, [params]);
  
  const handleResetCamera = useCallback(() => {
    // Camera reset is handled by OrbitControls internal reset
    window.location.reload();
  }, []);
  
  return (
    <div className="h-screen w-screen blueprint-grid vignette grain-overlay overflow-hidden">
      <Header />
      
      <main className="pt-16 h-full flex">
        {/* Left Panel - Chat + Prompt */}
        <div className="w-[35%] h-full bg-[#11161D] hairline-r flex flex-col">
          <PromptPanel onGenerate={handleGenerate} isGenerating={isGenerating} />
          <ParameterControls params={params} onParamsChange={setParams} />
        </div>
        
        {/* Right Panel - 3D Viewport */}
        <div className="w-[65%] h-full relative">
          <div className="canvas-container">
            <Canvas
              camera={{ position: [60, 50, 60], fov: 45 }}
              gl={{ antialias: true, alpha: true }}
              style={{ background: '#0D1117' }}
            >
              <Scene params={params} wireframe={wireframe} />
            </Canvas>
          </div>
          
          <ViewportOverlay
            is3D={is3D}
            onToggle3D={() => setIs3D(!is3D)}
            wireframe={wireframe}
            onToggleWireframe={() => setWireframe(!wireframe)}
            onResetCamera={handleResetCamera}
            params={params}
          />
        </div>
      </main>
    </div>
  );
}

export default App;