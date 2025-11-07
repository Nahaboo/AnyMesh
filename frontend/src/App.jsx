import { useState } from 'react'
import ConfigSidebar from './components/ConfigSidebar'
import ViewerLayout from './components/ViewerLayout'
import { simplifyMesh, generateMesh, segmentMesh, retopologizeMesh, pollTaskStatus } from './utils/api'
import './styles/v2-theme.css'

/**
 * App - Main application component
 * Two-stage workflow: Configuration → Visualization
 */
function App() {
  // View management: 'config' or 'viewer'
  const [currentView, setCurrentView] = useState('config')

  // Configuration data from first page
  const [configData, setConfigData] = useState(null)

  // Mesh data
  const [meshInfo, setMeshInfo] = useState(null)
  const [originalMeshInfo, setOriginalMeshInfo] = useState(null)  // Keep original mesh reference
  const [sessionInfo, setSessionInfo] = useState(null)

  // Task management
  const [currentTask, setCurrentTask] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Handler when config is complete
  const handleConfigComplete = (config) => {
    console.log('[App] Configuration complete:', config)
    setConfigData(config)

    if (config.type === 'file') {
      // File uploaded, prepare for visualization
      setMeshInfo(config.data)
      setOriginalMeshInfo(config.data)  // Save original mesh info
      setSessionInfo(null)
    } else if (config.type === 'images') {
      // Images uploaded, prepare for generation
      setSessionInfo(config.data)
      setMeshInfo(null)
      setOriginalMeshInfo(null)
    }

    // Switch to viewer
    setCurrentView('viewer')
  }

  // Handler to go back home
  const handleHomeClick = () => {
    // Reset everything
    setCurrentView('config')
    setConfigData(null)
    setMeshInfo(null)
    setOriginalMeshInfo(null)
    setSessionInfo(null)
    setCurrentTask(null)
    setIsProcessing(false)
  }

  // Handler for mesh simplification
  const handleSimplify = async (params) => {
    console.log('[App] Starting simplification:', params)
    setIsProcessing(true)

    try {
      const response = await simplifyMesh(params)
      console.log('[App] Task created:', response)

      const taskId = response.task_id

      // Poll task status
      await pollTaskStatus(
        taskId,
        (task) => {
          console.log('[App] Task update:', task)
          // Add task type to identify which operation this is
          setCurrentTask({ ...task, taskType: 'simplify' })

          // Task completed - don't auto-load the simplified mesh
          // User will click a button to load it if they want
          if (task.status === 'completed' && task.result) {
            console.log('[App] Simplification completed:', task.result)
          }
        },
        1000
      )

      setIsProcessing(false)
    } catch (error) {
      console.error('[App] Simplification error:', error)
      setIsProcessing(false)
      setCurrentTask({
        id: 'error',
        status: 'failed',
        error: error.message || 'An error occurred',
        taskType: 'simplify'
      })
    }
  }

  // Handler to load the simplified mesh result
  const handleLoadSimplified = () => {
    if (!currentTask || currentTask.status !== 'completed' || !currentTask.result) {
      console.error('[App] No completed task to load')
      return
    }

    const result = currentTask.result

    // Le backend convertit automatiquement en GLB
    // Remplacer l'extension par .glb pour charger le fichier converti
    const originalName = result.output_filename
    const glbName = originalName.replace(/\.[^.]+$/, '.glb')

    const simplifiedMeshInfo = {
      filename: glbName,  // Fichier GLB converti pour la visualisation
      displayFilename: originalName,  // Nom original pour l'affichage
      file_size: result.output_size || 0,
      format: originalMeshInfo.format,  // Format du mesh ORIGINAL (avant simplification)
      vertices_count: result.vertices_count || result.simplified?.vertices || 0,
      faces_count: result.faces_count || result.simplified?.triangles || 0,
      triangles_count: result.faces_count || result.simplified?.triangles || 0,  // Pour compatibilité avec SimplificationControls
      bounding_box: meshInfo.bounding_box,
      uploadId: Date.now(),
      isSimplified: true,  // Flag to indicate this is from /mesh/output
      originalFilename: originalName  // Fichier source simplifié (bunny_simplified.obj)
    }

    console.log('[App] Loading simplified mesh (GLB):', simplifiedMeshInfo)

    // IMPORTANT: Update originalMeshInfo to the simplified mesh
    // This allows chaining operations (simplify → retopologize)
    setOriginalMeshInfo(simplifiedMeshInfo)
    setMeshInfo(simplifiedMeshInfo)
  }

  // Handler to reload the original mesh
  const handleLoadOriginal = () => {
    if (!originalMeshInfo) {
      console.error('[App] No original mesh to load')
      return
    }

    console.log('[App] Reloading original mesh:', originalMeshInfo)
    // Reload original mesh with new uploadId to force refresh
    setMeshInfo({
      ...originalMeshInfo,
      uploadId: Date.now()
    })
  }

  // Handler for mesh segmentation
  const handleSegment = async (params) => {
    console.log('[App] Starting segmentation:', params)
    setIsProcessing(true)

    try {
      const response = await segmentMesh(params)
      console.log('[App] Task created:', response)

      const taskId = response.task_id

      // Poll task status
      await pollTaskStatus(
        taskId,
        (task) => {
          console.log('[App] Task update:', task)
          setCurrentTask({ ...task, taskType: 'segment' })

          // Task completed
          if (task.status === 'completed' && task.result) {
            console.log('[App] Segmentation completed:', task.result)
          }
        },
        1000
      )

      setIsProcessing(false)
    } catch (error) {
      console.error('[App] Segmentation error:', error)
      setIsProcessing(false)
      setCurrentTask({
        id: 'error',
        status: 'failed',
        error: error.message || 'An error occurred',
        taskType: 'segment'
      })
    }
  }

  // Handler to load the segmented mesh result
  const handleLoadSegmented = () => {
    if (!currentTask || currentTask.status !== 'completed' || !currentTask.result) {
      console.error('[App] No completed task to load')
      return
    }

    const result = currentTask.result
    console.log('[App] Task result:', result)

    // Ensure we have originalMeshInfo
    if (!originalMeshInfo) {
      console.error('[App] No original mesh info available')
      return
    }

    // Check if output_filename exists
    if (!result.output_filename) {
      console.error('[App] No output_filename in task result')
      return
    }

    const segmentedMeshInfo = {
      filename: result.output_filename,
      file_size: result.output_size || 0,
      format: originalMeshInfo.format || '.obj',
      vertices_count: originalMeshInfo.vertices_count || 0,
      faces_count: originalMeshInfo.faces_count || originalMeshInfo.triangles_count || 0,
      triangles_count: originalMeshInfo.triangles_count || originalMeshInfo.faces_count || 0,
      bounding_box: originalMeshInfo.bounding_box,
      uploadId: Date.now(),
      isSegmented: true,
      num_segments: result.num_segments,
      method: result.method
    }

    console.log('[App] Loading segmented mesh:', segmentedMeshInfo)
    setMeshInfo(segmentedMeshInfo)
  }

  // Handler for mesh retopology
  const handleRetopologize = async (params) => {
    console.log('[App] Starting retopology:', params)
    setIsProcessing(true)

    try {
      const response = await retopologizeMesh(params)
      console.log('[App] Task created:', response)

      const taskId = response.task_id

      // Store output filename for later loading
      if (response.output_filename) {
        setMeshInfo(prev => ({
          ...prev,
          retopologizedFilename: response.output_filename
        }))
      }

      // Poll task status
      await pollTaskStatus(
        taskId,
        (task) => {
          console.log('[App] Task update:', task)
          setCurrentTask({ ...task, taskType: 'retopology' })

          // Task completed - don't auto-load the retopologized mesh
          // User will click a button to load it if they want
          if (task.status === 'completed' && task.result) {
            console.log('[App] Retopology completed:', task.result)
          }
        },
        1000
      )

      setIsProcessing(false)
    } catch (error) {
      console.error('[App] Retopology error:', error)
      setIsProcessing(false)
      setCurrentTask({
        id: 'error',
        status: 'failed',
        error: error.message || 'An error occurred',
        taskType: 'retopology'
      })
    }
  }

  // Handler to load the retopologized mesh result
  const handleLoadRetopologized = () => {
    if (!currentTask || currentTask.status !== 'completed' || !currentTask.result) {
      console.error('[App] No completed task to load')
      return
    }

    const result = currentTask.result

    // Le backend convertit automatiquement en GLB
    // Remplacer l'extension par .glb pour charger le fichier converti
    const originalName = result.output_filename  // Ex: bunny_retopo.obj
    const glbName = originalName.replace(/\.[^.]+$/, '.glb')  // Ex: bunny_retopo.glb

    const retopologizedMeshInfo = {
      filename: originalName,  // Nom du fichier original (bunny_retopo.obj) - pour référence
      displayFilename: glbName,  // Fichier GLB converti - c'est ce qui sera chargé par RenderModeController
      file_size: result.output_size || 0,
      format: originalMeshInfo.format,  // Format du mesh ORIGINAL (avant retopologie)
      vertices_count: result.vertices_count,
      faces_count: result.faces_count,
      triangles_count: result.faces_count,  // Pour compatibilité
      bounding_box: meshInfo.bounding_box,
      uploadId: Date.now(),
      isRetopologized: true,  // Flag to indicate this is from /mesh/output (retopologized)
      originalFilename: originalName  // Fichier source retopologisé (bunny_retopo.obj)
    }

    console.log('[App] Loading retopologized mesh (GLB):', retopologizedMeshInfo)
    setMeshInfo(retopologizedMeshInfo)
  }

  // Handler for mesh generation
  const handleGenerate = async (params) => {
    console.log('[App] Starting generation:', params)
    setIsProcessing(true)

    try {
      const response = await generateMesh(params)
      console.log('[App] Task created:', response)

      const taskId = response.task_id

      // Poll task status
      await pollTaskStatus(
        taskId,
        (task) => {
          console.log('[App] Task update:', task)
          setCurrentTask({ ...task, taskType: 'generate' })

          // If task is completed, prepare mesh for display
          if (task.status === 'completed' && task.result) {
            const generatedMeshInfo = {
              filename: task.result.output_filename,
              displayFilename: task.result.output_filename,
              file_size: 0,
              format: `.${params.outputFormat}`,
              vertices_count: task.result.vertices_count,
              faces_count: task.result.faces_count,
              bounding_box: null,
              uploadId: Date.now(),
              isGenerated: true
            }
            setMeshInfo(generatedMeshInfo)
          }
        },
        1000
      )

      setIsProcessing(false)
    } catch (error) {
      console.error('[App] Generation error:', error)
      setIsProcessing(false)
      setCurrentTask({
        id: 'error',
        status: 'failed',
        error: error.message || 'An error occurred',
        taskType: 'generate'
      })
    }
  }

  return (
    <div className="v2-app">
      {currentView === 'config' ? (
        <ConfigSidebar onConfigComplete={handleConfigComplete} />
      ) : (
        <ViewerLayout
          meshInfo={meshInfo}
          sessionInfo={sessionInfo}
          configData={configData}
          onHomeClick={handleHomeClick}
          onSimplify={handleSimplify}
          onGenerate={handleGenerate}
          onSegment={handleSegment}
          onRetopologize={handleRetopologize}
          onLoadSimplified={handleLoadSimplified}
          onLoadSegmented={handleLoadSegmented}
          onLoadRetopologized={handleLoadRetopologized}
          onLoadOriginal={handleLoadOriginal}
          currentTask={currentTask}
          isProcessing={isProcessing}
        />
      )}
    </div>
  )
}

export default App
