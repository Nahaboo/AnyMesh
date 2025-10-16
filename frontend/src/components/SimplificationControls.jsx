import { useState } from 'react'

function SimplificationControls({ meshInfo, onSimplify, isProcessing }) {
  const [reductionRatio, setReductionRatio] = useState(0.5)
  const [preserveBoundary, setPreserveBoundary] = useState(true)

  // Vérifier si le format est GLTF/GLB (non supporté pour la simplification)
  const isGltfFormat = meshInfo?.format === '.gltf' || meshInfo?.format === '.glb'

  const handleSubmit = (e) => {
    e.preventDefault()

    if (onSimplify && !isGltfFormat) {
      // Utiliser originalFilename pour la simplification (fichier source, pas GLB)
      const filenameForSimplification = meshInfo.originalFilename || meshInfo.filename
      console.log('[DEBUG] Simplification du fichier:', filenameForSimplification)

      onSimplify({
        filename: filenameForSimplification,
        reduction_ratio: reductionRatio,
        preserve_boundary: preserveBoundary
      })
    }
  }

  // Calcul du nombre estimé de triangles après simplification
  const estimatedTriangles = meshInfo.triangles_count
    ? Math.round(meshInfo.triangles_count * (1 - reductionRatio))
    : 0

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">
        Parametres de simplification
      </h2>

      {/* Avertissement pour GLTF/GLB */}
      {isGltfFormat && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
          <div className="flex items-start space-x-3">
            <svg className="w-5 h-5 text-yellow-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-yellow-800 mb-1">
                Format non supporte pour la simplification
              </h3>
              <p className="text-sm text-yellow-700">
                Les fichiers GLTF/GLB peuvent etre visualises mais ne peuvent pas etre simplifies.
                Open3D supporte uniquement les formats OBJ, STL, PLY et OFF pour la simplification.
              </p>
            </div>
          </div>
        </div>
      )}

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
            disabled={isProcessing || isGltfFormat}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500 disabled:opacity-50"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0%</span>
            <span>50%</span>
            <span>95%</span>
          </div>
        </div>

        {/* Estimation */}
        {meshInfo.triangles_count && (
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
        )}

        {/* Options avancees */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Options avancees</h3>

          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={preserveBoundary}
              onChange={(e) => setPreserveBoundary(e.target.checked)}
              disabled={isProcessing || isGltfFormat}
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
          disabled={isProcessing || !meshInfo || isGltfFormat}
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
