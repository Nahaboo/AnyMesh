import { Suspense } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import CameraController from './CameraController'
import RenderModeController from './RenderModeController'

/**
 * CameraSync - Component that syncs camera rotation to parent
 */
function CameraSync({ onCameraUpdate }) {
  const { camera } = useThree()

  useFrame(() => {
    if (onCameraUpdate && camera) {
      onCameraUpdate(camera.quaternion)
    }
  })

  return null
}

/**
 * MeshViewer - 3D viewer with render mode support
 * Supports: solid, wireframe, normal, smooth rendering modes + custom shaders
 */
function MeshViewer({ meshInfo, renderMode = 'solid', shaderParams = {}, onCameraUpdate }) {
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
      <Canvas camera={{ position: [3, 3, 3], fov: 50 }}>
        {/* Camera sync for axes widget */}
        <CameraSync onCameraUpdate={onCameraUpdate} />

        {/* Camera auto-adjustment */}
        {meshInfo.bounding_box && <CameraController boundingBox={meshInfo.bounding_box} />}

        {/* Lighting - Uniform ambient light for better performance */}
        {/* Matcap materials (solid/flat) don't need directional lights */}
        <ambientLight intensity={1.0} />

        {/* 3D Model with render mode */}
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
          <RenderModeController
            filename={meshInfo.displayFilename || meshInfo.filename}
            isGenerated={meshInfo.isGenerated || false}
            isSimplified={meshInfo.isSimplified || false}
            isRetopologized={meshInfo.isRetopologized || false}
            isSegmented={meshInfo.isSegmented || false}
            renderMode={renderMode}
            shaderParams={shaderParams}
            uploadId={meshInfo.uploadId}
          />
        </Suspense>

        {/* Camera Controls */}
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={0.1}
          maxDistance={200}
        />
      </Canvas>
    </div>
  )
}

export default MeshViewer
