import React, { useState } from 'react'
import TopToolbar from './TopToolbar'
import LeftToolbar from './LeftToolbar'
import BottomToolbar from './BottomToolbar'
import MeshViewer from './MeshViewer'
import AxesWidget from './AxesWidget'
import SimplificationControls from './SimplificationControls'
import SegmentationControls from './SegmentationControls'
import MeshGenerationControls from './MeshGenerationControls'
import RetopologyControls from './RetopologyControls'
import TaskStatus from './TaskStatus'
import * as THREE from 'three'
import { useShaderDebugGUI } from '../hooks/useShaderDebugGUI'
import { getMaterialShader } from '../shaders/materials'

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
  onSegment,
  onRetopologize,
  onLoadSimplified,
  onLoadSegmented,
  onLoadRetopologized,
  onLoadOriginal,
  onLoadParent,
  onMeshSaved,
  currentTask,
  isProcessing
}) {

  const [renderMode, setRenderMode] = useState('solid')
  const [activeTool, setActiveTool] = useState('simplification')
  const [showRefinePanel, setShowRefinePanel] = useState(false)
  const [cameraQuaternion, setCameraQuaternion] = useState(new THREE.Quaternion())
  const [shaderParams, setShaderParams] = useState({})
  const [debugMode, setDebugMode] = useState(false)

  // Get active shader config
  const isShaderMode = renderMode.startsWith('shader:')
  const shaderId = isShaderMode ? renderMode.split(':')[1] : null
  const shaderConfig = shaderId ? getMaterialShader(shaderId) : null

  const handleCameraUpdate = (quaternion) => {
    setCameraQuaternion(quaternion.clone())
  }

  const handleToolChange = (tool) => {
    setActiveTool(tool)
    // Show refine panel when Simplification, Segmentation, or Retopoly is selected
    setShowRefinePanel(tool === 'simplification' || tool === 'segmentation' || tool === 'retopoly')
  }

  // Auto-show refine panel when in images mode
  React.useEffect(() => {
    if (configData?.type === 'images' && sessionInfo) {
      setShowRefinePanel(true)
      setActiveTool('generation')  // Set tool to 'generation' for images mode
    }
  }, [configData, sessionInfo])

  // Handler for shader parameter changes from debug GUI
  const handleShaderParamChange = (key, value) => {
    if (value === 'RESET_ALL') {
      // Reset to defaults
      setShaderParams({})
      console.log('[ViewerLayout] Shader params reset to defaults')
    } else {
      // Update specific parameter
      setShaderParams(prev => ({
        ...prev,
        [key]: value
      }))
    }
  }

  // Initialize shader debug GUI
  useShaderDebugGUI(
    shaderConfig,
    shaderParams,
    handleShaderParamChange,
    debugMode && isShaderMode
  )

  // Keyboard shortcut: Ctrl+D to toggle debug mode
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl+D (or Cmd+D on Mac)
      if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault()
        if (isShaderMode) {
          setDebugMode(prev => {
            const newValue = !prev
            console.log(`[ViewerLayout] Debug mode ${newValue ? 'enabled' : 'disabled'}`)
            return newValue
          })
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [debugMode, isShaderMode])

  const handleExport = (format) => {
    if (!meshInfo) return

    // Build export URL with format conversion
    const isGenerated = meshInfo.isGenerated || false
    const isSimplified = meshInfo.isSimplified || false
    const isRetopologized = meshInfo.isRetopologized || false
    const isSegmented = meshInfo.isSegmented || false
    const exportUrl = `http://localhost:8000/export/${meshInfo.filename}?format=${format.id}&is_generated=${isGenerated}&is_simplified=${isSimplified}&is_retopologized=${isRetopologized}&is_segmented=${isSegmented}`

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
        debugMode={debugMode}
        onDebugModeChange={setDebugMode}
        isShaderMode={isShaderMode}
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
          meshInfo={meshInfo}
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
            shaderParams={shaderParams}
            onCameraUpdate={handleCameraUpdate}
          />

          {/* Bottom Toolbar (overlaid) */}
          <BottomToolbar
            meshInfo={meshInfo}
            onExport={handleExport}
            onMeshSaved={onMeshSaved}
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
                {activeTool === 'simplification' ? 'Simplification' :
                 activeTool === 'segmentation' ? 'Segmentation' :
                 activeTool === 'retopoly' ? 'Retopology' :
                 activeTool === 'generation' ? 'Generate 3D Mesh' : 'Tool'}
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

            {/* Content based on config type and active tool */}
            {configData?.type === 'file' && meshInfo ? (
              activeTool === 'simplification' ? (
                <SimplificationControls
                  meshInfo={meshInfo}
                  onSimplify={onSimplify}
                  onLoadSimplified={onLoadSimplified}
                  onLoadOriginal={onLoadOriginal}
                  currentTask={currentTask}
                  isProcessing={isProcessing}
                />
              ) : activeTool === 'segmentation' ? (
                <SegmentationControls
                  meshInfo={meshInfo}
                  onSegment={onSegment}
                  onLoadSegmented={onLoadSegmented}
                  onLoadOriginal={onLoadParent}
                  currentTask={currentTask}
                  isProcessing={isProcessing}
                />
              ) : activeTool === 'retopoly' ? (
                <RetopologyControls
                  meshInfo={meshInfo}
                  onRetopologize={onRetopologize}
                  onLoadRetopologized={onLoadRetopologized}
                  onLoadOriginal={onLoadParent}
                  currentTask={currentTask}
                  isProcessing={isProcessing}
                />
              ) : null
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
                  activeTool={activeTool}
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
