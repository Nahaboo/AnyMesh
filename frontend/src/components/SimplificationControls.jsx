import { useState } from 'react'

function SimplificationControls({ meshInfo, onSimplify, onLoadSimplified, onLoadOriginal, currentTask, isProcessing }) {
  // Niveaux de simplification: 0 = Basse, 1 = Moyenne, 2 = Forte
  const [simplificationLevel, setSimplificationLevel] = useState(1)
  const [preserveBoundary, setPreserveBoundary] = useState(true)

  // Mapper les niveaux vers des ratios de réduction
  const levelToRatio = {
    0: 0.3,   // Basse: supprime 30% (garde 70%)
    1: 0.5,   // Moyenne: supprime 50% (garde 50%)
    2: 0.8    // Forte: supprime 80% (garde 20%)
  }

  const levelLabels = ['Basse', 'Moyenne', 'Forte']
  const reductionRatio = levelToRatio[simplificationLevel]

  // Vérifier si le format est GLTF/GLB (non supporté pour la simplification)
  const isGltfFormat = meshInfo?.format === '.gltf' || meshInfo?.format === '.glb'

  // Vérifier si on visualise un mesh déjà simplifié
  const isSimplifiedMesh = meshInfo?.isSimplified === true

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
  // Utiliser triangles_count ou faces_count (selon la source du mesh)
  const currentTriangles = meshInfo?.triangles_count || meshInfo?.faces_count || 0
  const estimatedTriangles = currentTriangles > 0
    ? Math.round(currentTriangles * (1 - reductionRatio))
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

      {/* Avertissement pour mesh déjà simplifié */}
      {isSimplifiedMesh && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex items-start space-x-3">
            <svg className="w-5 h-5 text-blue-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-blue-800 mb-1">
                Modèle simplifié affiché
              </h3>
              <p className="text-sm text-blue-700">
                Vous visualisez actuellement le modèle simplifié. Pour effectuer une nouvelle simplification, retournez d'abord au modèle original en cliquant sur le bouton ci-dessous.
              </p>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Slider de simplification */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Simplification: <span className="text-blue-600 font-semibold">{levelLabels[simplificationLevel]}</span>
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="1"
            value={simplificationLevel}
            onChange={(e) => setSimplificationLevel(parseInt(e.target.value))}
            disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500 disabled:opacity-50"
          />
          <div className="flex justify-between text-xs text-gray-600 mt-2 font-medium">
            <span>Basse</span>
            <span>Moyenne</span>
            <span>Forte</span>
          </div>
          <div className="text-xs text-gray-500 mt-2 text-center">
            {simplificationLevel === 0 && "Garde 70% des triangles (qualité élevée)"}
            {simplificationLevel === 1 && "Garde 50% des triangles (équilibre)"}
            {simplificationLevel === 2 && "Garde 20% des triangles (fichier léger)"}
          </div>
        </div>

        {/* Estimation - Affichée uniquement sur le mesh original */}
        {currentTriangles > 0 && !isSimplifiedMesh && (
          <div className="bg-blue-50 rounded-lg p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Triangles actuels:</span>
              <span className="font-semibold text-gray-900">
                {currentTriangles.toLocaleString()}
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
                ~{(currentTriangles - estimatedTriangles).toLocaleString()}
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
              disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
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
          disabled={isProcessing || !meshInfo || isGltfFormat || isSimplifiedMesh}
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

        {/* Boutons de navigation entre modèles */}
        <div className="space-y-2">
          {/* Bouton pour charger le résultat simplifié */}
          {currentTask && currentTask.status === 'completed' && currentTask.result && !meshInfo?.isSimplified && (
            <button
              type="button"
              onClick={onLoadSimplified}
              className="w-full bg-green-500 hover:bg-green-600 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center space-x-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <span>Charger le résultat simplifié</span>
            </button>
          )}

          {/* Bouton pour recharger le modèle original */}
          {meshInfo?.isSimplified && (
            <button
              type="button"
              onClick={onLoadOriginal}
              className="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center space-x-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Charger le modèle original</span>
            </button>
          )}
        </div>
      </form>
    </div>
  )
}

export default SimplificationControls
