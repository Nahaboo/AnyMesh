import React, { useState } from 'react'
import { API_BASE_URL } from '../utils/api'
import TopToolbar from './TopToolbar'
import LeftToolbar from './LeftToolbar'
import BottomToolbar from './BottomToolbar'
import MeshViewer from './MeshViewer'
import AxesWidget from './AxesWidget'
import SimplificationControls from './SimplificationControls'
import SegmentationControls from './SegmentationControls'
import MeshGenerationControls from './MeshGenerationControls'
import RetopologyControls from './RetopologyControls'
import PromptGenerationControls from './PromptGenerationControls'
import PhysicsControls, { MATERIAL_PRESETS } from './PhysicsControls'
import TexturingControls from './TexturingControls'
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
  const [cameraPosition, setCameraPosition] = useState(new THREE.Vector3(3, 3, 3))
  const [shaderParams, setShaderParams] = useState({})
  const [debugMode, setDebugMode] = useState(false)
  const [autoRotate, setAutoRotate] = useState(false)
  const [hdriPreset, setHdriPreset] = useState('studio')

  // Physics state
  const [physicsGravity, setPhysicsGravity] = useState(-9.81)
  const [physicsMass, setPhysicsMass] = useState(1.0)
  const [physicsRestitution, setPhysicsRestitution] = useState(0.1)
  const [physicsDamping, setPhysicsDamping] = useState(0.5)
  const [physicsPreset, setPhysicsPreset] = useState(null)

  const [physicsResetKey, setPhysicsResetKey] = useState(0)
  const [texturePreset, setTexturePreset] = useState(null)

  const activePresetObj = physicsPreset ? MATERIAL_PRESETS.find(p => p.id === physicsPreset) : null
  // Track last applied visual material (preset or AI) so sliders don't reset appearance
  const [lastMaterialPreset, setLastMaterialPreset] = useState(null)

  // Get active shader config
  const isShaderMode = renderMode.startsWith('shader:')
  const shaderId = isShaderMode ? renderMode.split(':')[1] : null
  const shaderConfig = shaderId ? getMaterialShader(shaderId) : null

  const handleCameraUpdate = (quaternion, position) => {
    setCameraQuaternion(quaternion.clone())
    if (position) setCameraPosition(position.clone())
  }

  const handleToolChange = (tool) => {
    setActiveTool(tool)
    setShowRefinePanel(tool === 'simplification' || tool === 'segmentation' || tool === 'retopoly' || tool === 'physics' || tool === 'texturing')
  }

  const isPhysicsMode = activeTool === 'physics'

  const handlePhysicsPresetChange = (preset) => {
    setPhysicsMass(preset.mass)
    setPhysicsRestitution(preset.restitution)
    setPhysicsDamping(preset.damping)
    setPhysicsPreset(preset.id)
    setTexturePreset(null)
    setLastMaterialPreset(preset)
  }

  const handleMassChange = (v) => { setPhysicsMass(v); setPhysicsPreset(null) }
  const handleRestitutionChange = (v) => { setPhysicsRestitution(v); setPhysicsPreset(null) }
  const handleDampingChange = (v) => { setPhysicsDamping(v); setPhysicsPreset(null) }

  const handleResetMaterial = () => {
    setPhysicsPreset(null)
    setTexturePreset(null)
    setLastMaterialPreset(null)
  }

  const handlePhysicsReset = () => {
    setPhysicsResetKey(prev => prev + 1)
  }

  const handlePhysicsExit = () => {
    setPhysicsResetKey(0)
    setActiveTool('simplification')
    setShowRefinePanel(false)
    // If a material preset was active, switch to textured mode so it stays visible
    if (activePresetObj || texturePreset || lastMaterialPreset) {
      setRenderMode('textured')
    }
  }

  const handleTextureApply = ({ textureId, scale, blendSharpness }) => {
    setPhysicsPreset(null)
    setTexturePreset({
      id: `ai-${textureId}`,
      visual: { color: '#ffffff', metalness: 0.0, roughness: 0.5 },
      procedural: {
        type: 'ai-generated',
        customTextureUrls: { color: `${API_BASE_URL}/texture/generated/${textureId}/color.png` },
        scale: scale || 3.0,
        blendSharpness: blendSharpness || 2.0
      }
    })
  }

  const handleAIMaterialGenerated = ({ textureId, physics }) => {
    setPhysicsMass(physics.mass)
    setPhysicsRestitution(physics.restitution)
    setPhysicsDamping(physics.damping)
    setPhysicsPreset(null)
    const aiPreset = {
      id: `ai-${textureId}`,
      visual: { color: '#ffffff', metalness: 0.0, roughness: 0.5 },
      procedural: {
        type: 'ai-generated',
        customTextureUrls: { color: `${API_BASE_URL}/texture/generated/${textureId}/color.png` },
        scale: 3.0,
        blendSharpness: 2.0
      }
    }
    setTexturePreset(aiPreset)
    setLastMaterialPreset(aiPreset)
  }

  // Auto-show refine panel when in images or prompt mode
  React.useEffect(() => {
    if (configData?.type === 'images' && sessionInfo) {
      setShowRefinePanel(true)
      setActiveTool('generation')  // Set tool to 'generation' for images mode
    }
    if (configData?.type === 'prompt') {
      setShowRefinePanel(true)
      setActiveTool('prompt-generation')
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
        setDebugMode(prev => {
          const newValue = !prev
          console.log(`[ViewerLayout] Debug mode ${newValue ? 'enabled' : 'disabled'}`)
          return newValue
        })
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
    const exportUrl = `${API_BASE_URL}/export/${meshInfo.filename}?format=${format.id}&is_generated=${isGenerated}&is_simplified=${isSimplified}&is_retopologized=${isRetopologized}&is_segmented=${isSegmented}`

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
        onRenderModeChange={(mode) => { setRenderMode(mode) }}
        onHomeClick={onHomeClick}
        debugMode={debugMode}
        onDebugModeChange={setDebugMode}
        isShaderMode={isShaderMode}
        disabled={isPhysicsMode}
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
            autoRotate={autoRotate}
            debugMode={debugMode}
            physicsMode={isPhysicsMode}
            hdriPreset={hdriPreset}
            materialPreset={renderMode === 'textured' ? (activePresetObj || texturePreset || lastMaterialPreset) : null}
            physicsProps={isPhysicsMode ? {
              meshInfo,
              gravity: physicsGravity,
              density: physicsMass,
              restitution: physicsRestitution,
              damping: physicsDamping,
              hdriPreset,
              resetKey: physicsResetKey,
              materialPreset: activePresetObj || texturePreset || lastMaterialPreset
            } : null}
          />

          {/* Bottom Toolbar (overlaid) */}
          <BottomToolbar
            meshInfo={meshInfo}
            onExport={handleExport}
            onMeshSaved={onMeshSaved}
            autoRotate={autoRotate}
            onAutoRotateToggle={() => setAutoRotate(prev => !prev)}
            hdriPreset={hdriPreset}
            onHdriChange={setHdriPreset}
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
                 activeTool === 'physics' ? 'Physics Simulation' :
                 activeTool === 'texturing' ? 'AI Texturing' :
                 activeTool === 'generation' ? 'Generate 3D Mesh' :
                 activeTool === 'prompt-generation' ? 'Generate from Prompt' : 'Tool'}
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
              ) : activeTool === 'physics' ? (
                <PhysicsControls
                  gravity={physicsGravity}
                  onGravityChange={setPhysicsGravity}
                  mass={physicsMass}
                  onMassChange={handleMassChange}
                  restitution={physicsRestitution}
                  onRestitutionChange={handleRestitutionChange}
                  damping={physicsDamping}
                  onDampingChange={handleDampingChange}
                  activePreset={physicsPreset}
                  onPresetChange={handlePhysicsPresetChange}
                  onResetMaterial={handleResetMaterial}
                  onAIMaterialGenerated={handleAIMaterialGenerated}
                  onReset={handlePhysicsReset}
                  onExit={handlePhysicsExit}
                />
              ) : activeTool === 'texturing' ? (
                <TexturingControls
                  meshInfo={meshInfo}
                  onApplyTexture={handleTextureApply}
                  isProcessing={isProcessing}
                />
              ) : null
            ) : configData?.type === 'images' && sessionInfo ? (
              <MeshGenerationControls
                sessionInfo={sessionInfo}
                onGenerate={onGenerate}
                isProcessing={isProcessing}
              />
            ) : configData?.type === 'prompt' ? (
              <PromptGenerationControls
                onGenerate={onGenerate}
                isProcessing={isProcessing}
                currentTask={currentTask}
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
