import { useEffect, useRef, useState } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
// @ts-expect-error - no types available yet
import occtimportjs from 'occt-import-js';
// @ts-expect-error - three.js JSM modules lack type declarations
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils';

interface STEPLoaderProps {
  url: string;
  showEdges?: boolean;
  showWireframe?: boolean;
  onLoad?: () => void;
  onError?: (error: string) => void;
}

export default function STEPLoader({
  url,
  showEdges = false,
  showWireframe = false,
  onLoad,
  onError,
}: STEPLoaderProps) {
  const meshRef = useRef<THREE.Group>(null);
  const { camera } = useThree();
  const [geometries, setGeometries] = useState<{ mesh: THREE.BufferGeometry, edges: THREE.BufferGeometry | null }[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [scale, setScale] = useState(1);

  // Store callbacks in refs to avoid re-running the effect
  const onLoadRef = useRef(onLoad);
  const onErrorRef = useRef(onError);
  useEffect(() => { onLoadRef.current = onLoad; }, [onLoad]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  useEffect(() => {
    let active = true;

    async function loadStep() {
      try {
        // Step 1: Async fetch the STEP binary
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const buffer = await response.arrayBuffer();
        const fileData = new Uint8Array(buffer);

        // Step 2: Async WASM initialization
        const occt = await occtimportjs();
        
        // Step 3: Parse STEP file (CPU-intensive)
        const result = occt.ReadStepFile(fileData, null);
        
        if (!active) return;
        
        if (!result.success || !result.meshes) {
          throw new Error('Failed to parse STEP file');
        }

        // Step 4: Build geometries asynchronously in batches
        // using requestIdleCallback to keep UI responsive
        const parsedGeometries: { mesh: THREE.BufferGeometry, edges: THREE.BufferGeometry | null }[] = [];
        const totalBox = new THREE.Box3();
        totalBox.makeEmpty();

        // Process meshes in idle callbacks for large models
        const processMeshBatch = (startIdx: number): Promise<void> => {
          return new Promise((resolve) => {
            const processNext = () => {
              if (!active) return resolve();
              
              const batchEnd = Math.min(startIdx + 3, result.meshes.length);
              
              for (let i = startIdx; i < batchEnd; i++) {
                const resultMesh = result.meshes[i];
                const geometry = new THREE.BufferGeometry();
                
                geometry.setAttribute('position', new THREE.Float32BufferAttribute(resultMesh.attributes.position.array, 3));
                
                if (resultMesh.attributes.normal) {
                  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(resultMesh.attributes.normal.array, 3));
                } else {
                  geometry.computeVertexNormals();
                }

                if (resultMesh.index) {
                  geometry.setIndex(new THREE.Uint32BufferAttribute(resultMesh.index.array, 1));
                }

                // Smooth normals
                let finalGeo = geometry;
                try {
                  finalGeo = mergeVertices(geometry, 1e-4);
                  finalGeo.computeVertexNormals();
                } catch (e) {
                  console.warn("Failed to merge vertices, using flat geometry", e);
                }

                finalGeo.computeBoundingBox();
                if (finalGeo.boundingBox) {
                  totalBox.union(finalGeo.boundingBox);
                }

                // Create edge geometry with lower angle threshold for crisp CAD edges
                const edgeGeo = new THREE.EdgesGeometry(finalGeo, 20);
                parsedGeometries.push({ mesh: finalGeo, edges: edgeGeo });
              }

              if (batchEnd < result.meshes.length) {
                // Yield to browser, then continue
                if (typeof requestIdleCallback !== 'undefined') {
                  requestIdleCallback(() => {
                    processMeshBatch(batchEnd).then(resolve);
                  });
                } else {
                  setTimeout(() => {
                    processMeshBatch(batchEnd).then(resolve);
                  }, 0);
                }
              } else {
                resolve();
              }
            };

            processNext();
          });
        };

        await processMeshBatch(0);
        if (!active) return;

        // Step 5: Center the whole assembly
        const center = new THREE.Vector3();
        totalBox.getCenter(center);
        
        for (const item of parsedGeometries) {
          item.mesh.translate(-center.x, -center.y, -center.z);
          item.mesh.computeBoundingBox();
        }
        
        // Scale to fit
        const size = new THREE.Vector3();
        totalBox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const targetSize = 5;
        const normalizedScale = maxDim > 0 ? targetSize / maxDim : 1;

        setScale(normalizedScale);
        setGeometries(parsedGeometries);
        
        // Adjust camera
        camera.position.set(8, 6, 8);
        camera.updateProjectionMatrix();

        if (onLoadRef.current) onLoadRef.current();

      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load STEP';
        console.error("Error loading STEP:", err);
        if (active) {
            setError(err instanceof Error ? err : new Error(message));
            if (onErrorRef.current) onErrorRef.current(message);
        }
      }
    }

    loadStep();

    return () => {
      active = false;
    };
  }, [url, camera]);

  // Cleanup geometries on unmount
  useEffect(() => {
    return () => {
      geometries.forEach(g => {
        g.mesh.dispose();
        if (g.edges) g.edges.dispose();
      });
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error || geometries.length === 0) {
    return null;
  }

  return (
    <group scale={[scale, scale, scale]} ref={meshRef}>
      {geometries.map((geo, index) => (
        <group key={`geo-${index}`}>
          {/* Matte metallic CAD material — contrasts clearly against dark background */}
          <mesh geometry={geo.mesh} castShadow receiveShadow>
            <meshStandardMaterial
              color="#5c6878"
              metalness={0.4}
              roughness={0.72}
              envMapIntensity={0.6}
              side={THREE.DoubleSide}
              wireframe={showWireframe}
            />
          </mesh>
          
          {/* Crisp visible edge overlay */}
          {showEdges && geo.edges && (
            <lineSegments geometry={geo.edges}>
              <lineBasicMaterial
                color="#aabdd4"
                linewidth={1}
                transparent
                opacity={0.65}
              />
            </lineSegments>
          )}
        </group>
      ))}
    </group>
  );
}
