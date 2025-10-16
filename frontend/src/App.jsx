import { useState } from 'react'
import FileUpload from './components/FileUpload'
import MeshViewer from './components/MeshViewer'
import SimplificationControls from './components/SimplificationControls'
import TaskStatus from './components/TaskStatus'
import { simplifyMesh, pollTaskStatus } from './utils/api'

function App() {
  const [pendingMesh, setPendingMesh] = useState(null) // Fichier en attente de confirmation
  const [uploadedMesh, setUploadedMesh] = useState(null) // Fichier confirmé et chargé
  const [currentTask, setCurrentTask] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const handleUploadSuccess = (meshInfo) => {
    console.log('Fichier uploade:', meshInfo)
    // Mettre le fichier en attente de confirmation (ne pas charger encore)
    setPendingMesh(meshInfo)
  }

  const handleConfirmLoad = () => {
    // Ajouter un ID unique pour forcer le rechargement
    const meshWithId = {
      ...pendingMesh,
      uploadId: Date.now(), // Timestamp unique
      // displayFilename: pour la visualisation 3D (GLB si converti)
      displayFilename: pendingMesh.glb_filename || pendingMesh.filename,
      // originalFilename: pour la simplification (toujours le fichier source)
      originalFilename: pendingMesh.original_filename || pendingMesh.filename
    }
    console.log('[DEBUG] Chargement du mesh:', meshWithId.displayFilename, 'Original:', meshWithId.originalFilename)
    setUploadedMesh(meshWithId)
    setPendingMesh(null)
    // Reset task quand un nouveau fichier est uploade
    setCurrentTask(null)
  }

  const handleCancelLoad = () => {
    setPendingMesh(null)
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
          {/* Etape 1: Upload */}
          {!uploadedMesh && !pendingMesh && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center space-x-2 mb-4">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500 text-white font-bold text-sm">
                  1
                </div>
                <h2 className="text-xl font-semibold text-gray-800">
                  Uploader un fichier 3D
                </h2>
              </div>
              <FileUpload onUploadSuccess={handleUploadSuccess} />
            </div>
          )}

          {/* Etape 1.5: Prévisualisation et confirmation */}
          {pendingMesh && !uploadedMesh && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center space-x-2 mb-6">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500 text-white font-bold text-sm">
                  2
                </div>
                <h2 className="text-xl font-semibold text-gray-800">
                  Confirmer le chargement
                </h2>
              </div>

              {/* Informations du fichier */}
              <div className="bg-gray-50 rounded-lg p-6 mb-6">
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center">
                  <svg className="w-5 h-5 mr-2 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  Informations du fichier
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Nom du fichier:</p>
                    <p className="font-semibold text-gray-900">{pendingMesh.filename}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Format:</p>
                    <p className="font-semibold text-gray-900">{pendingMesh.format}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Taille du fichier:</p>
                    <p className="font-semibold text-gray-900">
                      {(pendingMesh.file_size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  {pendingMesh.vertices_count && (
                    <div>
                      <p className="text-sm text-gray-500">Vertices:</p>
                      <p className="font-semibold text-gray-900">
                        {pendingMesh.vertices_count.toLocaleString()}
                      </p>
                    </div>
                  )}
                  {pendingMesh.triangles_count && (
                    <div>
                      <p className="text-sm text-gray-500">Triangles:</p>
                      <p className="font-semibold text-gray-900">
                        {pendingMesh.triangles_count.toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>

                {/* Avertissements */}
                {pendingMesh.file_size > 10000000 && (
                  <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="flex items-start space-x-2">
                      <svg className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-red-800">Fichier très volumineux</p>
                        <p className="text-xs text-red-700 mt-1">
                          Ce fichier est très gros ({(pendingMesh.file_size / 1024 / 1024).toFixed(1)} MB). Le chargement peut prendre longtemps et causer des ralentissements. Il est fortement recommandé de simplifier le fichier d'abord.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                {pendingMesh.file_size > 5000000 && pendingMesh.file_size <= 10000000 && (
                  <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <div className="flex items-start space-x-2">
                      <svg className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-yellow-800">Fichier de taille moyenne</p>
                        <p className="text-xs text-yellow-700 mt-1">
                          Le chargement peut prendre quelques secondes.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Boutons d'action */}
              <div className="flex space-x-4">
                <button
                  onClick={handleConfirmLoad}
                  className="flex-1 bg-blue-500 hover:bg-blue-600 text-white font-medium py-3 px-6 rounded-lg transition-colors flex items-center justify-center space-x-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>Charger le fichier 3D</span>
                </button>
                <button
                  onClick={handleCancelLoad}
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-3 px-6 rounded-lg transition-colors flex items-center justify-center space-x-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  <span>Annuler</span>
                </button>
              </div>
            </div>
          )}

          {/* Etape 2: Visualisation + Simplification */}
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
