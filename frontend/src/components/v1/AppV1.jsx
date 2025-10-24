import { useState } from 'react'
import FileUpload from './components/FileUpload'
import ImageUpload from './components/ImageUpload'
import MeshViewer from './components/MeshViewer'
import SimplificationControls from './components/SimplificationControls'
import MeshGenerationControls from './components/MeshGenerationControls'
import TaskStatus from './components/TaskStatus'
import { simplifyMesh, generateMesh, pollTaskStatus } from './utils/api'

function App() {
  // Mode de l'application: 'file' (classique) ou 'generate' (génération depuis images)
  const [mode, setMode] = useState('file')

  // États pour mode fichier classique
  const [uploadedMesh, setUploadedMesh] = useState(null) // Fichier chargé

  // États pour mode génération
  const [sessionInfo, setSessionInfo] = useState(null) // Info session images
  const [generatedMesh, setGeneratedMesh] = useState(null) // Maillage généré

  // États partagés
  const [currentTask, setCurrentTask] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Handlers pour mode fichier classique
  const handleUploadSuccess = (meshInfo) => {
    console.log('🟢 [App] Fichier uploadé avec succès:', meshInfo)
    setUploadedMesh(meshInfo)
    setCurrentTask(null)
  }

  // Handlers pour mode génération
  const handleImagesUploadSuccess = (sessionData) => {
    console.log('🟢 [App] Images uploadées avec succès:', sessionData)
    setSessionInfo(sessionData)
    setCurrentTask(null)
  }

  const handleGenerate = async (params) => {
    console.log('Lancement génération:', params)
    setIsProcessing(true)

    try {
      // Lancer la tâche de génération
      const response = await generateMesh(params)
      console.log('Tâche créée:', response)

      const taskId = response.task_id

      // Polling du statut de la tâche
      await pollTaskStatus(
        taskId,
        (task) => {
          console.log('Update tâche:', task)
          setCurrentTask(task)

          // Si la tâche est complétée, préparer l'affichage du maillage
          if (task.status === 'completed' && task.result) {
            const meshInfo = {
              filename: task.result.output_filename,
              displayFilename: task.result.output_filename,
              file_size: 0, // Non disponible immédiatement
              format: `.${params.outputFormat}`,
              vertices_count: task.result.vertices_count,
              faces_count: task.result.faces_count,
              bounding_box: null, // Sera calculé au chargement
              uploadId: Date.now(),
              isGenerated: true // Flag pour utiliser l'endpoint /mesh/generated/
            }
            setGeneratedMesh(meshInfo)
          }
        },
        1000
      )

      setIsProcessing(false)
    } catch (error) {
      console.error('Erreur génération:', error)
      setIsProcessing(false)
      setCurrentTask({
        id: 'error',
        status: 'failed',
        error: error.message || 'Une erreur est survenue'
      })
    }
  }

  const handleSimplify = async (params) => {
    console.log('Lancement simplification:', params)
    setIsProcessing(true)

    try {
      // Lancer la tache de simplification
      const response = await simplifyMesh(params)
      console.log('Tache creee:', response)

      const taskId = response.task_id

      // Polling du statut de la tache
      await pollTaskStatus(
        taskId,
        (task) => {
          console.log('Update tache:', task)
          setCurrentTask(task)
        },
        1000 // Polling toutes les secondes
      )

      setIsProcessing(false)
    } catch (error) {
      console.error('Erreur simplification:', error)
      setIsProcessing(false)
      // Afficher l'erreur dans la tache
      setCurrentTask({
        id: 'error',
        status: 'failed',
        error: error.message || 'Une erreur est survenue'
      })
    }
  }

  const handleTaskComplete = (task) => {
    console.log('Tache completee:', task)
    setIsProcessing(false)
  }

  // Handler pour basculer entre les modes
  const handleModeChange = (newMode) => {
    setMode(newMode)
    // Reset les états selon le mode
    if (newMode === 'file') {
      setSessionInfo(null)
      setGeneratedMesh(null)
    } else {
      setUploadedMesh(null)
    }
    setCurrentTask(null)
    setIsProcessing(false)
  }

  // Déterminer quel mesh afficher (classique ou généré)
  const displayedMesh = mode === 'file' ? uploadedMesh : generatedMesh

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                MeshSimplifier
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                Simplification et visualisation de maillages 3D + Génération depuis images
              </p>
            </div>

            {/* Toggle mode */}
            <div className="flex items-center space-x-4">
              {(uploadedMesh || sessionInfo) && (
                <div className="flex items-center space-x-1 text-green-600">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="font-medium text-sm">
                    {mode === 'file' ? 'Fichier chargé' : 'Images chargées'}
                  </span>
                </div>
              )}

              <div className="flex bg-gray-100 rounded-lg p-1">
                <button
                  onClick={() => handleModeChange('file')}
                  className={`
                    px-4 py-2 rounded-md text-sm font-medium transition-colors
                    ${mode === 'file'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                    }
                  `}
                >
                  Fichier 3D
                </button>
                <button
                  onClick={() => handleModeChange('generate')}
                  className={`
                    px-4 py-2 rounded-md text-sm font-medium transition-colors
                    ${mode === 'generate'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                    }
                  `}
                >
                  Générer depuis images
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          {/* MODE FICHIER 3D */}
          {mode === 'file' && (
            <>
              {/* Upload fichier */}
              {!uploadedMesh && (
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <h2 className="text-xl font-semibold text-gray-800">
                      Uploader un fichier 3D
                    </h2>
                  </div>
                  <FileUpload onUploadSuccess={handleUploadSuccess} />
                </div>
              )}

              {/* Visualisation + Simplification */}
              {uploadedMesh && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <MeshViewer meshInfo={uploadedMesh} />
                  <div className="space-y-6">
                    <SimplificationControls
                      meshInfo={uploadedMesh}
                      onSimplify={handleSimplify}
                      isProcessing={isProcessing}
                    />
                    {currentTask && (
                      <TaskStatus
                        task={currentTask}
                        onComplete={handleTaskComplete}
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Bouton pour recommencer */}
              {uploadedMesh && (
                <div className="text-center">
                  <button
                    onClick={() => {
                      setUploadedMesh(null)
                      setCurrentTask(null)
                      setIsProcessing(false)
                    }}
                    className="inline-flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    <span>Uploader un nouveau fichier</span>
                  </button>
                </div>
              )}
            </>
          )}

          {/* MODE GÉNÉRATION DEPUIS IMAGES */}
          {mode === 'generate' && (
            <>
              {/* Upload images */}
              {!sessionInfo && (
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <h2 className="text-xl font-semibold text-gray-800">
                      Uploader des images
                    </h2>
                  </div>
                  <ImageUpload onUploadSuccess={handleImagesUploadSuccess} />
                </div>
              )}

              {/* Génération + Visualisation */}
              {sessionInfo && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Si maillage généré, afficher le viewer */}
                  {generatedMesh ? (
                    <MeshViewer meshInfo={generatedMesh} />
                  ) : (
                    <div className="bg-white rounded-lg shadow p-6 flex items-center justify-center min-h-[400px]">
                      <div className="text-center text-gray-500">
                        <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                        </svg>
                        <p className="text-lg font-medium">Aucun maillage généré</p>
                        <p className="text-sm mt-2">Cliquez sur "Générer le modèle 3D" pour commencer</p>
                      </div>
                    </div>
                  )}

                  {/* Contrôles de génération */}
                  <div className="space-y-6">
                    <MeshGenerationControls
                      sessionInfo={sessionInfo}
                      onGenerate={handleGenerate}
                      isProcessing={isProcessing}
                    />
                    {currentTask && (
                      <TaskStatus
                        task={currentTask}
                        onComplete={handleTaskComplete}
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Bouton pour recommencer */}
              {sessionInfo && (
                <div className="text-center">
                  <button
                    onClick={() => {
                      setSessionInfo(null)
                      setGeneratedMesh(null)
                      setCurrentTask(null)
                      setIsProcessing(false)
                    }}
                    className="inline-flex items-center space-x-2 text-sm text-purple-600 hover:text-purple-800 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span>Uploader de nouvelles images</span>
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <p>MeshSimplifier - Simplification de maillages 3D avec Open3D</p>
            <div className="flex items-center space-x-4">
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-gray-900 transition-colors"
              >
                API Docs
              </a>
              <span className="text-gray-300">|</span>
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                <span>Backend actif</span>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
