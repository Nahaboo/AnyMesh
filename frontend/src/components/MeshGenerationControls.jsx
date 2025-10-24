import { useState } from 'react'

function MeshGenerationControls({ sessionInfo, onGenerate, isProcessing }) {
  const [resolution, setResolution] = useState('medium')
  const [outputFormat, setOutputFormat] = useState('obj')

  const handleGenerate = () => {
    if (onGenerate) {
      onGenerate({
        sessionId: sessionInfo.sessionId,
        resolution,
        outputFormat
      })
    }
  }

  // Estimation du temps de génération
  const estimatedTime = {
    low: '10-30 sec',
    medium: '30-60 sec',
    high: '1-3 min'
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">
        Générer un modèle 3D
      </h2>

      {/* Informations de session */}
      {sessionInfo && (
        <div className="mb-6 p-4 bg-purple-50 rounded-lg">
          <div className="flex items-center space-x-2 text-sm text-purple-800">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">
              {sessionInfo.imagesCount} image(s) prête(s) pour la génération
            </span>
          </div>
        </div>
      )}

      {/* Contrôles de génération */}
      <div className="space-y-4">
        {/* Résolution */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Résolution du maillage
          </label>
          <div className="grid grid-cols-3 gap-2">
            {['low', 'medium', 'high'].map((res) => (
              <button
                key={res}
                onClick={() => setResolution(res)}
                disabled={isProcessing}
                className={`
                  py-2 px-3 rounded-lg text-sm font-medium transition-colors
                  ${resolution === res
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }
                  ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
                `}
              >
                {res === 'low' && 'Basse'}
                {res === 'medium' && 'Moyenne'}
                {res === 'high' && 'Haute'}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Temps estimé: {estimatedTime[resolution]}
          </p>
        </div>

        {/* Format de sortie */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Format de sortie
          </label>
          <div className="grid grid-cols-3 gap-2">
            {['obj', 'stl', 'ply'].map((format) => (
              <button
                key={format}
                onClick={() => setOutputFormat(format)}
                disabled={isProcessing}
                className={`
                  py-2 px-3 rounded-lg text-sm font-medium uppercase transition-colors
                  ${outputFormat === format
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }
                  ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
                `}
              >
                {format}
              </button>
            ))}
          </div>
        </div>

        {/* Note importante */}
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start space-x-2">
            <svg className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
            <div className="text-xs text-blue-800">
              <p className="font-medium">Note MVP:</p>
              <p className="mt-1">
                La génération actuelle utilise une approche basique (depth map).
                Pour de meilleurs résultats, utilisez plusieurs images avec différents angles.
              </p>
            </div>
          </div>
        </div>

        {/* Bouton de génération */}
        <button
          onClick={handleGenerate}
          disabled={isProcessing || !sessionInfo}
          className="w-full bg-purple-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-purple-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          {isProcessing ? (
            <>
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span>Génération en cours...</span>
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
              <span>Générer le modèle 3D</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default MeshGenerationControls
