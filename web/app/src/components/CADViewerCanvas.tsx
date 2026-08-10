import { useRef, useState, useEffect, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  OrbitControls,
  Grid,
  Center,
  BakeShadows,
  PerformanceMonitor,
  Html,
  OrthographicCamera,
  PerspectiveCamera,
} from "@react-three/drei";
import * as THREE from "three";
// @ts-expect-error - three.js JSM modules lack type declarations
import { STLLoader } from "three/examples/jsm/loaders/STLLoader";
// @ts-expect-error - three.js JSM modules lack type declarations
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils";
import "./CADViewer.css";
import STEPLoader from "./STEPLoader";

// ============================================
// TYPES
// ============================================
export type ShadingMode = "solid" | "wireframe" | "xray";

interface STLModelProps {
  url: string;
  showEdges: boolean;
  showWireframe?: boolean;
  xrayMode?: boolean;
  flatShading?: boolean;
  onLoad?: () => void;
  onError?: (error: string) => void;
}

export interface CADViewerCanvasProps {
  stlUrl: string | null;
  stepUrl?: string | null;
  isLoading: boolean;
  hasModel: boolean;
  showWireframe?: boolean;
  showAxes?: boolean;
  showEdges: boolean;
  shadingMode?: ShadingMode;
  isOrtho?: boolean;
  showGrid?: boolean;
  showShadows?: boolean;
  autoRotate?: boolean;
  fitView?: number;        // increment to trigger fit-to-view
  cameraTarget: [number, number, number] | null;
  onCameraReached: () => void;
  onModelLoaded: () => void;
  onModelError: (error: string) => void;
  modelLoaded: boolean;
}

// ============================================
// Camera Controller (one-shot smooth transition)
// ============================================
function CameraController({
  targetPosition,
  onReached,
}: {
  targetPosition: [number, number, number] | null;
  onReached: () => void;
}) {
  const { camera } = useThree();
  const targetRef = useRef<THREE.Vector3 | null>(null);

  useEffect(() => {
    if (targetPosition) {
      targetRef.current = new THREE.Vector3(...targetPosition);
    }
  }, [targetPosition]);

  useFrame(() => {
    if (!targetRef.current) return;
    camera.position.lerp(targetRef.current, 0.08);
    const distance = camera.position.distanceTo(targetRef.current);
    if (distance < 0.05) {
      camera.position.copy(targetRef.current);
      targetRef.current = null;
      onReached();
    }
  });

  return null;
}

// ============================================
// STL Model Component
// ============================================
function STLModel({
  url,
  showEdges,
  showWireframe = false,
  xrayMode = false,
  flatShading = false,
  onLoad,
  onError,
}: STLModelProps) {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [scale, setScale] = useState(1);
  const meshRef = useRef<THREE.Mesh>(null);
  const { camera } = useThree();

  const edgesGeometry = useMemo(() => {
    if (!geometry) return null;
    return new THREE.EdgesGeometry(geometry, 20);
  }, [geometry]);

  useEffect(() => {
    if (!url) return;

    setGeometry(null);
    setError(null);

    const loader = new STLLoader();
    loader.load(
      url,
      (geo: THREE.BufferGeometry) => {
        geo.computeBoundingBox();
        geo.center();

        let processedGeo: THREE.BufferGeometry;
        try {
          processedGeo = mergeVertices(geo, 1e-4);
          processedGeo.computeVertexNormals();
        } catch {
          geo.computeVertexNormals();
          processedGeo = geo;
        }

        processedGeo.computeBoundingBox();
        const boundingBox = processedGeo.boundingBox!;
        const size = new THREE.Vector3();
        boundingBox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const targetSize = 5;
        const normalizedScale = maxDim > 0 ? targetSize / maxDim : 1;

        setScale(normalizedScale);
        setGeometry(processedGeo);

        camera.position.set(8, 6, 8);
        camera.updateProjectionMatrix();

        onLoad?.();
      },
      undefined,
      (err: unknown) => {
        console.error("Failed to load STL:", err);
        setError(err as Error);
        onError?.("Failed to load 3D model");
      },
    );
  }, [url, onLoad, onError, camera]);

  if (error || !geometry) {
    return null;
  }

  return (
    <group scale={[scale, scale, scale]}>
      <mesh ref={meshRef} geometry={geometry} castShadow receiveShadow>
        <meshStandardMaterial
          color={xrayMode ? "#8ab4d4" : "#5c6878"}
          metalness={xrayMode ? 0.1 : 0.4}
          roughness={xrayMode ? 0.3 : 0.72}
          envMapIntensity={0.6}
          side={THREE.DoubleSide}
          wireframe={showWireframe}
          transparent={xrayMode}
          opacity={xrayMode ? 0.38 : 1.0}
          depthWrite={!xrayMode}
          flatShading={flatShading}
        />
      </mesh>

      {/* Second solid layer for xray — shows opaque structure inside */}
      {xrayMode && (
        <mesh geometry={geometry} castShadow={false} receiveShadow={false}>
          <meshStandardMaterial
            color="#2a3a4a"
            metalness={0.1}
            roughness={0.8}
            side={THREE.BackSide}
            transparent
            opacity={0.15}
            depthWrite={false}
          />
        </mesh>
      )}

      {/* Edge overlay */}
      {showEdges && edgesGeometry && (
        <lineSegments geometry={edgesGeometry}>
          <lineBasicMaterial
            color={xrayMode ? "#5da9e9" : "#aabdd4"}
            linewidth={1}
            transparent
            opacity={xrayMode ? 0.9 : 0.65}
          />
        </lineSegments>
      )}
    </group>
  );
}

// ============================================
// Placeholder Model
// ============================================
function PlaceholderModel() {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.15;
      meshRef.current.rotation.x =
        Math.sin(state.clock.elapsedTime * 0.1) * 0.05;
    }
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[1.8, 1]} />
      <meshStandardMaterial
        color="#1a1a24"
        metalness={0.4}
        roughness={0.5}
        wireframe
      />
    </mesh>
  );
}

// ============================================
// Loading Spinner (HTML Overlay)
// ============================================
function LoadingSpinner() {
  return (
    <Html center>
      <div className="modern-loader">
        <div className="loader-ring"></div>
      </div>
    </Html>
  );
}


// ============================================
// Fit View Helper (auto-zooms camera to fit model bounds)
// ============================================
function FitViewHelper({ trigger }: { trigger?: number }) {
  const { camera, scene } = useThree();

  useEffect(() => {
    if (!trigger) return;
    const box = new THREE.Box3().setFromObject(scene);
    if (box.isEmpty()) return;

    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = (camera as THREE.PerspectiveCamera).fov;
    const distance = fov ? maxDim / (2 * Math.tan((fov * Math.PI) / 360)) * 1.5 : maxDim * 2;

    camera.position.set(center.x + distance * 0.5, center.y + distance * 0.4, center.z + distance * 0.5);
    camera.lookAt(center);
    camera.updateProjectionMatrix();
  }, [trigger, camera, scene]);

  return null;
}

// ============================================
// Main Canvas Component (lazy-loaded)
// ============================================
export default function CADViewerCanvas({
  stlUrl,
  stepUrl,
  isLoading,
  showWireframe = false,
  showAxes = false,
  showEdges,
  shadingMode = "solid",
  isOrtho = false,
  showGrid = true,
  showShadows = true,
  autoRotate = false,
  fitView,
  cameraTarget,
  onCameraReached,
  onModelLoaded,
  onModelError,
  modelLoaded,
}: CADViewerCanvasProps) {
  const [dpr, setDpr] = useState(1.5);
  const [modelError, setModelError] = useState<string | null>(null);

  const handleModelError = (error: string) => {
    setModelError(error);
    onModelError(error);
  };

  const xrayMode = shadingMode === "xray";
  const wireframeActive = showWireframe || shadingMode === "wireframe";



  return (
    <>
      <Canvas
        gl={{
          antialias: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: xrayMode ? 1.6 : 1.3,
        }}
        dpr={dpr}
        shadows={showShadows}
        onCreated={({ gl }) => {
          gl.setClearColor('#1a1a1e');
          const canvas = gl.domElement;
          canvas.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            console.warn('WebGL context lost — waiting for restore...');
          });
          canvas.addEventListener('webglcontextrestored', () => {
            gl.setClearColor('#1a1a1e');
          });
        }}
      >
        <PerformanceMonitor onIncline={() => setDpr(2)} onDecline={() => setDpr(1)} />
        {modelLoaded && showShadows && <BakeShadows />}

        {/* Camera — switch between perspective and orthographic */}
        {isOrtho ? (
          <OrthographicCamera
            makeDefault
            position={[8, 6, 8]}
            zoom={40}
            near={0.01}
            far={10000}
          />
        ) : (
          <PerspectiveCamera
            makeDefault
            position={[8, 6, 8]}
            fov={45}
            near={0.01}
            far={10000}
          />
        )}

        {/* Lighting — slightly different for xray */}
        <ambientLight intensity={xrayMode ? 1.8 : 1.2} color="#e8eef5" />
        <directionalLight
          position={[10, 15, 8]}
          intensity={xrayMode ? 1.2 : 2.0}
          castShadow={showShadows}
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
          shadow-bias={-0.0001}
          color="#fffaf0"
        />
        <directionalLight
          position={[-8, 8, -4]}
          intensity={0.6}
          color="#c8d8f0"
        />
        <directionalLight
          position={[0, -4, -10]}
          intensity={0.4}
          color="#8aa8cc"
        />

        {showGrid && (
          <Grid
            args={[50, 50]}
            cellSize={1}
            cellThickness={0.4}
            cellColor="#1e1e22"
            sectionSize={5}
            sectionThickness={0.8}
            sectionColor="#28282e"
            fadeDistance={60}
            fadeStrength={1.2}
            followCamera={false}
            position={[0, -0.01, 0]}
          />
        )}

        <axesHelper args={[20]} visible={showAxes} />

        <Center>
          {isLoading ? (
            <LoadingSpinner />
          ) : (stepUrl || stlUrl) && !modelError ? (
            stepUrl ? (
              <STEPLoader
                url={stepUrl}
                showEdges={showEdges}
                showWireframe={wireframeActive}
                onLoad={() => onModelLoaded()}
                onError={handleModelError}
              />
            ) : (
              <STLModel
                url={stlUrl!}
                showEdges={showEdges}
                showWireframe={wireframeActive}
                xrayMode={xrayMode}
                flatShading={false}
                onLoad={() => onModelLoaded()}
                onError={handleModelError}
              />
            )
          ) : (
            <PlaceholderModel />
          )}
        </Center>

        <CameraController targetPosition={cameraTarget} onReached={onCameraReached} />

        <OrbitControls
          enableDamping
          dampingFactor={0.06}
          minDistance={0.5}
          maxDistance={500}
          enablePan={true}
          panSpeed={0.8}
          rotateSpeed={0.5}
          autoRotate={autoRotate}
          autoRotateSpeed={1.5}
          target={[0, 0, 0]}
        />

        <FitViewHelper trigger={fitView} />
      </Canvas>
    </>
  );
}
