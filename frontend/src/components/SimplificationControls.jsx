import { useState } from 'react'

function SimplificationControls({ meshInfo, onSimplify, isProcessing }) {
  const [reductionRatio, setReductionRatio] = useState(0.5)
  const [preserveBoundary, setPreserveBoundary] = useState(true)

  const handleSubmit = (e) => {
    e.preventDefault()

    if (onSimplify) {
      onSimplify({
        filename: meshInfo.filename,
        reduction_ratio: reductionRatio,
        preserve_boundary: preserveBoundary
      })
    }
  }

  // Calcul du nombre estimé de triangles après simplification
  const estimatedTriangles = Math.round(meshInfo.triangles_count * (1 - reductionRatio))

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">
        Parametres de simplification
      </h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Slider de reduction */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Taux de reduction: {(reductionRatio * 100).toFixed(0)}%
          </label>
          <input
            type="range"
            min="0"
            max="0.95"
            step="0.05"
            value={reductionRatio}
            onChange={(e) => setReductionRatio(parseFloat(e.target.value))}
            disabled={isProcessing}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500 disabled:opacity-50"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0%</span>
            <span>50%</span>
            <span>95%</span>
          </div>
        </div>

        {/* Estimation */}
        <div className="bg-blue-50 rounded-lg p-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Triangles actuels:</span>
            <span className="font-semibold text-gray-900">
              {meshInfo.triangles_count.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Triangles après simplification:</span>
            <span className="font-semibold text-blue-600">
              ~{estimatedTriangles.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Triangles supprimés:</span>
            <span className="font-semibold text-red-600">
              ~{(meshInfo.triangles_count - estimatedTriangles).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Options avancees */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Options avancees</h3>

          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={preserveBoundary}
              onChange={(e) => setPreserveBoundary(e.target.checked)}
              disabled={isProcessing}
              className="w-4 h-4 text-blue-500 border-gray-300 rounded focus:ring-blue-500 disabled:opacity-50"
            />
            <span className="text-sm text-gray-700">
              Preserver les bords du maillage
            </span>
          </label>
        </div>

        {/* Bouton de simplification */}
        <button
          type="submit"
          disabled={isProcessing || !meshInfo}
          className="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium py-3 px-4 rounded-lg transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          {isProcessing ? (
            <>
              <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Simplification en cours...</span>
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Lancer la simplification</span>
            </>
          )}
        </button>
      </form>
    </div>
  )
}

export default SimplificationControls
