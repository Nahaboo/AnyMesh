import { useState } from 'react'
import TopToolbar from './TopToolbar'
import LeftToolbar from './LeftToolbar'
import BottomToolbar from './BottomToolbar'
import MeshViewer from './MeshViewer'
import AxesWidget from './AxesWidget'
import SimplificationControls from './SimplificationControls'
import MeshGenerationControls from './MeshGenerationControls'
import TaskStatus from './TaskStatus'
import * as THREE from 'three'

/**
 * ViewerLayout - Main layout for the 3D visualization page
 * Includes: TopToolbar, LeftToolbar, BottomToolbar, and central viewer
 */
function ViewerLayout({
  meshInfo,
  sessionInfo,
  configData,
  onHomeClick,
  onSimplify,
  onGenerate,
  currentTask,
  isProcessing
}) {
  const [renderMode, setRenderMode] = useState('solid')
  const [activeTool, setActiveTool] = useState('refine')
  const [showRefinePanel, setShowRefinePanel] = useState(false)
  const [cameraQuaternion, setCameraQuaternion] = useState(new THREE.Quaternion())

  const handleCameraUpdate = (quaternion) => {
    setCameraQuaternion(quaternion.clone())
  }

  const handleToolChange = (tool) => {
    setActiveTool(tool)
    // Show refine panel when Refine is selected
    setShowRefinePanel(tool === 'refine')
  }

  const handleExport = (format) => {
    if (!meshInfo) return

    // Build export URL with format conversion
    const isGenerated = meshInfo.isGenerated || false
    const exportUrl = `http://localhost:8000/export/${meshInfo.filename}?format=${format.id}&is_generated=${isGenerated}`

    console.log(`[ViewerLayout] Exporting ${meshInfo.filename} as ${format.label}`)

    // Create temporary link and trigger download
    const link = document.createElement('a')
    link.href = exportUrl
    link.download = `${meshInfo.filename.split('.')[0]}${format.extension}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="v2-app" style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Top Toolbar */}
      <TopToolbar
        renderMode={renderMode}
        onRenderModeChange={setRenderMode}
        onHomeClick={onHomeClick}
      />

      {/* Main Content Area */}
      <div style={{
        flex: 1,
        display: 'flex',
        overflow: 'hidden',
        position: 'relative'
      }}>
        {/* Left Toolbar */}
        <LeftToolbar
          activeTool={activeTool}
          onToolChange={handleToolChange}
        />

        {/* Central Viewer */}
        <div style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden'
        }}>
          <MeshViewer
            meshInfo={meshInfo}
            renderMode={renderMode}
            onCameraUpdate={handleCameraUpdate}
          />

          {/* Bottom Toolbar (overlaid) */}
          <BottomToolbar
            meshInfo={meshInfo}
            onExport={handleExport}
            axesWidget={<AxesWidget mainCameraQuaternion={cameraQuaternion} />}
          />
        </div>

        {/* Right Panel - Refine/Generation Controls (Slide-in) */}
        {showRefinePanel && (
          <div style={{
            width: '360px',
            height: '100%',
            background: 'var(--v2-bg-secondary)',
            borderLeft: '1px solid var(--v2-border-secondary)',
            overflowY: 'auto',
            padding: 'var(--v2-spacing-lg)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--v2-spacing-lg)',
            boxShadow: 'var(--v2-shadow-lg)'
          }}>
            {/* Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingBottom: 'var(--v2-spacing-md)',
              borderBottom: '1px solid var(--v2-border-secondary)'
            }}>
              <h3 style={{
                fontSize: '1.125rem',
                fontWeight: 600,
                color: 'var(--v2-text-primary)'
              }}>
                Refine Mesh
              </h3>
              <button
                onClick={() => setShowRefinePanel(false)}
                className="v2-btn v2-btn-ghost"
                style={{ padding: 'var(--v2-spacing-xs)' }}
              >
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content based on config type */}
            {configData?.type === 'file' && meshInfo ? (
              <SimplificationControls
                meshInfo={meshInfo}
                onSimplify={onSimplify}
                isProcessing={isProcessing}
              />
            ) : configData?.type === 'images' && sessionInfo ? (
              <MeshGenerationControls
                sessionInfo={sessionInfo}
                onGenerate={onGenerate}
                isProcessing={isProcessing}
              />
            ) : (
              <div style={{
                padding: 'var(--v2-spacing-lg)',
                textAlign: 'center',
                color: 'var(--v2-text-muted)',
                fontSize: '0.875rem'
              }}>
                <p>No mesh loaded</p>
                <p style={{ marginTop: 'var(--v2-spacing-sm)', fontSize: '0.75rem' }}>
                  Return to home to upload a file or generate from images
                </p>
              </div>
            )}

            {/* Task Status */}
            {currentTask && (
              <div style={{
                marginTop: 'auto',
                paddingTop: 'var(--v2-spacing-lg)',
                borderTop: '1px solid var(--v2-border-secondary)'
              }}>
                <TaskStatus
                  task={currentTask}
                  onComplete={() => {}}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default ViewerLayout
