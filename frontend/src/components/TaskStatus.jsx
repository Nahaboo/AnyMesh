import { useEffect } from 'react'
import { getDownloadUrl } from '../utils/api'

function TaskStatus({ task, onComplete }) {
  useEffect(() => {
    // Notifier le parent quand la tache est completee
    if (task && task.status === 'completed' && onComplete) {
      onComplete(task)
    }
  }, [task, onComplete])

  if (!task) {
    return null
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-50 border-yellow-200 text-yellow-700'
      case 'processing':
        return 'bg-blue-50 border-blue-200 text-blue-700'
      case 'completed':
        return 'bg-green-50 border-green-200 text-green-700'
      case 'failed':
        return 'bg-red-50 border-red-200 text-red-700'
      default:
        return 'bg-gray-50 border-gray-200 text-gray-700'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
          </svg>
        )
      case 'processing':
        return (
          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        )
      case 'completed':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        )
      case 'failed':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        )
      default:
        return null
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'pending':
        return 'En attente'
      case 'processing':
        return 'En cours de traitement'
      case 'completed':
        return 'Terminé'
      case 'failed':
        return 'Échoué'
      default:
        return status
    }
  }

  const handleDownload = () => {
    if (task.result && task.result.output_file) {
      const filename = task.result.output_file.split('\\').pop().split('/').pop()
      window.open(getDownloadUrl(filename), '_blank')
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">
        Statut de la tâche
      </h2>

      {/* Statut */}
      <div className={`flex items-center space-x-3 p-4 rounded-lg border mb-4 ${getStatusColor(task.status)}`}>
        {getStatusIcon(task.status)}
        <div className="flex-1">
          <p className="font-medium">{getStatusText(task.status)}</p>
          {task.status === 'processing' && (
            <p className="text-sm mt-1">Progression: {task.progress}%</p>
          )}
        </div>
      </div>

      {/* Barre de progression */}
      {task.status === 'processing' && (
        <div className="mb-4">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${task.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Erreur */}
      {task.status === 'failed' && task.error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">{task.error}</p>
        </div>
      )}

      {/* Resultats */}
      {task.status === 'completed' && task.result && (
        <div className="space-y-4">
          {/* Statistiques */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">Original</p>
              <p className="text-sm font-semibold text-gray-900">
                {task.result.original_vertices?.toLocaleString()} vertices
              </p>
              <p className="text-sm font-semibold text-gray-900">
                {task.result.original_triangles?.toLocaleString()} triangles
              </p>
            </div>

            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-xs text-green-600 mb-1">Simplifié</p>
              <p className="text-sm font-semibold text-green-700">
                {task.result.simplified_vertices?.toLocaleString()} vertices
              </p>
              <p className="text-sm font-semibold text-green-700">
                {task.result.simplified_triangles?.toLocaleString()} triangles
              </p>
            </div>
          </div>

          {/* Reduction */}
          <div className="bg-blue-50 rounded-lg p-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Réduction</p>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Vertices supprimés:</span>
                <span className="font-semibold text-blue-700">
                  {task.result.vertices_removed?.toLocaleString()}
                  {task.result.vertices_ratio && ` (${(task.result.vertices_ratio * 100).toFixed(1)}%)`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Triangles supprimés:</span>
                <span className="font-semibold text-blue-700">
                  {task.result.triangles_removed?.toLocaleString()}
                  {task.result.triangles_ratio && ` (${(task.result.triangles_ratio * 100).toFixed(1)}%)`}
                </span>
              </div>
            </div>
          </div>

          {/* Bouton de telechargement */}
          <button
            onClick={handleDownload}
            className="w-full bg-green-500 hover:bg-green-600 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center space-x-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>Télécharger le maillage simplifié</span>
          </button>
        </div>
      )}

      {/* Info task ID */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          Task ID: <span className="font-mono">{task.id}</span>
        </p>
      </div>
    </div>
  )
}

export default TaskStatus
