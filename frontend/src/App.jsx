import { useState } from 'react'
import ConfigSidebar from './components/ConfigSidebar'
import ViewerLayout from './components/ViewerLayout'
import { simplifyMesh, generateMesh, pollTaskStatus } from './utils/api'
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
      setSessionInfo(null)
    } else if (config.type === 'images') {
      // Images uploaded, prepare for generation
      setSessionInfo(config.data)
      setMeshInfo(null)
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
          setCurrentTask(task)

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
        error: error.message || 'An error occurred'
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
      filename: glbName,  // Fichier GLB converti
      displayFilename: originalName,  // Nom original pour l'affichage
      file_size: result.output_size || 0,
      format: '.glb',  // Toujours GLB après conversion serveur
      vertices_count: result.vertices_count,
      faces_count: result.faces_count,
      bounding_box: meshInfo.bounding_box,
      uploadId: Date.now(),
      isSimplified: true,  // Flag to indicate this is from /mesh/output
      originalFilename: originalName
    }

    console.log('[App] Loading simplified mesh (GLB):', simplifiedMeshInfo)
    setMeshInfo(simplifiedMeshInfo)
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
          setCurrentTask(task)

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
        error: error.message || 'An error occurred'
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
          onLoadSimplified={handleLoadSimplified}
          currentTask={currentTask}
          isProcessing={isProcessing}
        />
      )}
    </div>
  )
}

export default App
