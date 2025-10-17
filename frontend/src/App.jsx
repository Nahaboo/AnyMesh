import { useState } from 'react'
import FileUpload from './components/FileUpload'
import MeshViewer from './components/MeshViewer'
import SimplificationControls from './components/SimplificationControls'
import TaskStatus from './components/TaskStatus'
import { simplifyMesh, pollTaskStatus } from './utils/api'

function App() {
  const [uploadedMesh, setUploadedMesh] = useState(null) // Fichier chargé
  const [currentTask, setCurrentTask] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const handleUploadSuccess = (meshInfo) => {
    console.log('🟢 [App] Fichier uploadé avec succès:', meshInfo)
    // Charger immédiatement le mesh (pas d'étape de confirmation)
    setUploadedMesh(meshInfo)
    // Reset task quand un nouveau fichier est uploadé
    setCurrentTask(null)
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
                Simplification et visualisation de maillages 3D
              </p>
            </div>
            {uploadedMesh && (
              <div className="flex items-center space-x-2 text-sm">
                <div className="flex items-center space-x-1 text-green-600">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="font-medium">Fichier charge</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          {/* Upload */}
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
              {/* Visualiseur 3D */}
              <MeshViewer meshInfo={uploadedMesh} />

              {/* Controles */}
              <div className="space-y-6">
                <SimplificationControls
                  meshInfo={uploadedMesh}
                  onSimplify={handleSimplify}
                  isProcessing={isProcessing}
                />

                {/* Statut de la tache */}
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
