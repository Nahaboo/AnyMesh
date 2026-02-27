import { Suspense, useState, useCallback, useRef } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows } from '@react-three/drei'
import CameraController from './CameraController'
import RenderModeController from './RenderModeController'
import ModelErrorBoundary from './ModelErrorBoundary'
import PhysicsPlayground from './PhysicsPlayground'

/**
 * CameraSync - Component that syncs camera rotation and position to parent
 */
function CameraSync({ onCameraUpdate }) {
  const { camera } = useThree()

  useFrame(() => {
    if (onCameraUpdate && camera) {
      onCameraUpdate(camera.quaternion, camera.position)
    }
  })

  return null
}

/**
 * GpuStatsBridge - Reads gl.info inside Canvas and pushes stats to parent via callback
 */
function GpuStatsBridge({ onStats }) {
  const { gl } = useThree()

  useFrame(() => {
    const { memory, render } = gl.info
    onStats({
      geometries: memory.geometries,
      textures: memory.textures,
      calls: render.calls,
      triangles: render.triangles
    })
  })

  return null
}

/**
 * MeshViewer - 3D viewer with render mode support
 * Supports: solid, wireframe, normal, smooth rendering modes + custom shaders
 */
function MeshViewer({ meshInfo, renderMode = 'solid', shaderParams = {}, onCameraUpdate, autoRotate = false, physicsMode = false, physicsProps = null, materialPreset = null, hdriPreset = 'studio', debugMode = false }) {
  const gpuStatsRef = useRef({ geometries: 0, textures: 0, calls: 0, triangles: 0 })
  const [gpuStats, setGpuStats] = useState({ geometries: 0, textures: 0, calls: 0, triangles: 0 })

  // Throttle GPU stats updates to avoid re-rendering every frame
  const frameCountRef = useRef(0)
  const handleGpuStats = useCallback((stats) => {
    gpuStatsRef.current = stats
    frameCountRef.current++
    if (frameCountRef.current % 30 === 0) {
      setGpuStats({ ...stats })
    }
  }, [])

  if (!meshInfo) {
    return (
      <div className="v2-viewer-container" style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{
          textAlign: 'center',
          color: 'var(--v2-text-muted)'
        }}>
          <svg
            width="64"
            height="64"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            style={{ margin: '0 auto', marginBottom: 'var(--v2-spacing-md)' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <p style={{ fontSize: '0.875rem', fontWeight: 500 }}>No 3D model loaded</p>
          <p style={{ fontSize: '0.75rem', marginTop: 'var(--v2-spacing-xs)' }}>
            Upload a file or generate from images to begin
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="v2-viewer-container" style={{
      width: '100%',
      height: '100%',
      position: 'relative'
    }}>
      {/* GPU monitor overlay - rendered outside Canvas as plain HTML */}
      {debugMode && (
        <div style={{
          position: 'absolute',
          top: 8,
          left: 8,
          background: 'rgba(0,0,0,0.8)',
          color: '#0f0',
          fontFamily: 'monospace',
          fontSize: 11,
          padding: '6px 10px',
          borderRadius: 4,
          lineHeight: 1.5,
          zIndex: 10,
          whiteSpace: 'nowrap',
          pointerEvents: 'none'
        }}>
          <div>GEO: {gpuStats.geometries} | TEX: {gpuStats.textures}</div>
          <div>DRAW: {gpuStats.calls} | TRI: {gpuStats.triangles.toLocaleString()}</div>
        </div>
      )}
      <Canvas shadows={{ type: THREE.PCFSoftShadowMap }} camera={{ position: [3, 3, 3], fov: 50 }}>
        {/* Camera sync for axes widget */}
        <CameraSync onCameraUpdate={onCameraUpdate} />

        {/* GPU stats bridge (reads gl.info and pushes to parent) */}
        {debugMode && <GpuStatsBridge onStats={handleGpuStats} />}

        {/* Camera auto-adjustment */}
        {meshInfo.bounding_box && <CameraController boundingBox={meshInfo.bounding_box} />}

        {/* Lighting - physics mode has its own lights in PhysicsPlayground */}
        {!physicsMode && <ambientLight intensity={materialPreset ? 0.3 : renderMode === 'textured' ? 1.5 : 1.0} />}
        {!physicsMode && <Environment preset={hdriPreset} background environmentIntensity={(materialPreset || renderMode === 'textured') ? (renderMode === 'textured' && !materialPreset ? 1.2 : 0.4) : 0.3} />}
        {!physicsMode && (materialPreset || renderMode === 'textured') && meshInfo.bounding_box && (
          <ContactShadows position={[0, -(meshInfo.bounding_box.diagonal * 0.5), 0]} scale={meshInfo.bounding_box.diagonal * 2} blur={2} opacity={0.4} far={meshInfo.bounding_box.diagonal * 2} />
        )}

        {physicsMode && physicsProps ? (
          <Suspense fallback={
            <group>
              <mesh>
                <boxGeometry args={[2, 2, 2]} />
                <meshStandardMaterial color="#6366f1" wireframe />
              </mesh>
            </group>
          }>
            <PhysicsPlayground key={physicsProps.resetKey} {...physicsProps} />
          </Suspense>
        ) : (
          <Suspense fallback={
            <group>
              <mesh>
                <boxGeometry args={[2, 2, 2]} />
                <meshStandardMaterial color="#6366f1" wireframe />
              </mesh>
              <mesh rotation={[0, Math.PI / 4, 0]}>
                <boxGeometry args={[1.5, 1.5, 1.5]} />
                <meshStandardMaterial color="#818cf8" wireframe />
              </mesh>
            </group>
          }>
            <ModelErrorBoundary>
              <RenderModeController
                filename={meshInfo.displayFilename || meshInfo.filename}
                isGenerated={meshInfo.isGenerated || false}
                isSimplified={meshInfo.isSimplified || false}
                isRetopologized={meshInfo.isRetopologized || false}
                isSegmented={meshInfo.isSegmented || false}
                renderMode={renderMode}
                shaderParams={shaderParams}
                uploadId={meshInfo.uploadId}
                materialPreset={materialPreset}
              />
            </ModelErrorBoundary>
          </Suspense>
        )}

        {/* Camera Controls */}
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={0.1}
          maxDistance={200}
          autoRotate={autoRotate}
          autoRotateSpeed={0.5}
        />
      </Canvas>
    </div>
  )
}

export default MeshViewer
