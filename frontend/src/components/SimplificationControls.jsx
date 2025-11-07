import { useState } from 'react'

function SimplificationControls({ meshInfo, onSimplify, onLoadSimplified, onLoadOriginal, currentTask, isProcessing }) {
  // Mode: 'standard' ou 'adaptive'
  const [mode, setMode] = useState('standard')

  // Niveaux de simplification: 0 = Basse, 1 = Moyenne, 2 = Forte
  const [simplificationLevel, setSimplificationLevel] = useState(1)
  const [preserveBoundary, setPreserveBoundary] = useState(true)

  // Paramètres mode adaptatif
  const [flatMultiplier, setFlatMultiplier] = useState(2.0)

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
      console.log(`[DEBUG] Simplification ${mode} du fichier:`, filenameForSimplification)

      if (mode === 'adaptive') {
        // Mode adaptatif
        onSimplify({
          mode: 'adaptive',
          filename: filenameForSimplification,
          target_ratio: reductionRatio,
          flat_multiplier: flatMultiplier
        })
      } else {
        // Mode standard
        onSimplify({
          mode: 'standard',
          filename: filenameForSimplification,
          reduction_ratio: reductionRatio,
          preserve_boundary: preserveBoundary
        })
      }
    }
  }

  // Calcul du nombre estimé de triangles après simplification
  // Utiliser triangles_count ou faces_count (selon la source du mesh)
  const currentTriangles = meshInfo?.triangles_count || meshInfo?.faces_count || 0
  const estimatedTriangles = currentTriangles > 0
    ? Math.round(currentTriangles * (1 - reductionRatio))
    : 0

  return (
    <div style={{
      background: 'var(--v2-bg-secondary)',
      borderRadius: 'var(--v2-radius-lg)',
      boxShadow: 'var(--v2-shadow-md)',
      padding: 'var(--v2-spacing-lg)'
    }}>
      <h2 style={{
        fontSize: '1.25rem',
        fontWeight: 600,
        color: 'var(--v2-text-primary)',
        marginBottom: 'var(--v2-spacing-md)'
      }}>
        Parametres de simplification
      </h2>

      {/* Toggle Mode Standard / Adaptatif */}
      <div style={{
        display: 'flex',
        gap: 'var(--v2-spacing-xs)',
        marginBottom: 'var(--v2-spacing-md)',
        background: 'var(--v2-bg-tertiary)',
        borderRadius: 'var(--v2-radius-lg)',
        padding: '4px'
      }}>
        <button
          type="button"
          onClick={() => setMode('standard')}
          disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
          style={{
            flex: 1,
            padding: 'var(--v2-spacing-sm)',
            borderRadius: 'var(--v2-radius-md)',
            border: 'none',
            background: mode === 'standard' ? 'var(--v2-accent-primary)' : 'transparent',
            color: mode === 'standard' ? '#ffffff' : 'var(--v2-text-secondary)',
            fontWeight: mode === 'standard' ? 600 : 500,
            fontSize: '0.875rem',
            cursor: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            opacity: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 0.5 : 1
          }}
        >
          Standard
        </button>
        <button
          type="button"
          onClick={() => setMode('adaptive')}
          disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
          style={{
            flex: 1,
            padding: 'var(--v2-spacing-sm)',
            borderRadius: 'var(--v2-radius-md)',
            border: 'none',
            background: mode === 'adaptive' ? 'var(--v2-accent-primary)' : 'transparent',
            color: mode === 'adaptive' ? '#ffffff' : 'var(--v2-text-secondary)',
            fontWeight: mode === 'adaptive' ? 600 : 500,
            fontSize: '0.875rem',
            cursor: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            opacity: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 0.5 : 1
          }}
        >
          Adaptatif
        </button>
      </div>

      {/* Description du mode adaptatif */}
      {mode === 'adaptive' && (
        <div style={{
          background: 'var(--v2-info-bg)',
          border: '1px solid var(--v2-info-border)',
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-md)',
          fontSize: '0.875rem',
          color: 'var(--v2-info-text)'
        }}>
          <strong style={{ display: 'block', marginBottom: '4px' }}>Mode adaptatif activé</strong>
          Détecte automatiquement les zones plates (murs, sols) et les simplifie plus agressivement que les zones courbes (détails, reliefs). Idéal pour les modèles architecturaux.
        </div>
      )}

      {/* Avertissement pour GLTF/GLB */}
      {isGltfFormat && (
        <div style={{
          background: 'var(--v2-warning-bg)',
          border: '1px solid var(--v2-warning-border)',
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-md)'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--v2-spacing-sm)' }}>
            <svg style={{ width: '20px', height: '20px', color: 'var(--v2-warning-text)', marginTop: '2px', flexShrink: 0 }} fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-warning-text)', marginBottom: '4px' }}>
                Format non supporte pour la simplification
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--v2-warning-text)' }}>
                Les fichiers GLTF/GLB peuvent etre visualises mais ne peuvent pas etre simplifies.
                Open3D supporte uniquement les formats OBJ, STL, PLY et OFF pour la simplification.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Avertissement pour mesh déjà simplifié */}
      {isSimplifiedMesh && (
        <div style={{
          background: 'var(--v2-info-bg)',
          border: '1px solid var(--v2-info-border)',
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-md)'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--v2-spacing-sm)' }}>
            <svg style={{ width: '20px', height: '20px', color: 'var(--v2-info-text)', marginTop: '2px', flexShrink: 0 }} fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-info-text)', marginBottom: '4px' }}>
                Modèle simplifié affiché
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--v2-info-text)' }}>
                Vous visualisez actuellement le modèle simplifié. Pour effectuer une nouvelle simplification, retournez d'abord au modèle original en cliquant sur le bouton ci-dessous.
              </p>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-lg)' }}>
        {/* Slider de simplification */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)',
            marginBottom: 'var(--v2-spacing-sm)'
          }}>
            Simplification: <span style={{ color: 'var(--v2-accent-primary)', fontWeight: 600 }}>{levelLabels[simplificationLevel]}</span>
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="1"
            value={simplificationLevel}
            onChange={(e) => setSimplificationLevel(parseInt(e.target.value))}
            disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
            style={{
              width: '100%',
              height: '8px',
              background: 'var(--v2-bg-tertiary)',
              borderRadius: 'var(--v2-radius-lg)',
              appearance: 'none',
              cursor: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 'not-allowed' : 'pointer',
              opacity: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 0.5 : 1,
              accentColor: 'var(--v2-accent-primary)'
            }}
          />
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            color: 'var(--v2-text-tertiary)',
            marginTop: 'var(--v2-spacing-xs)',
            fontWeight: 500
          }}>
            <span>Basse</span>
            <span>Moyenne</span>
            <span>Forte</span>
          </div>
          <div style={{
            fontSize: '0.75rem',
            color: 'var(--v2-text-muted)',
            marginTop: 'var(--v2-spacing-xs)',
            textAlign: 'center'
          }}>
            {simplificationLevel === 0 && "Garde 70% des triangles (qualité élevée)"}
            {simplificationLevel === 1 && "Garde 50% des triangles (équilibre)"}
            {simplificationLevel === 2 && "Garde 20% des triangles (fichier léger)"}
          </div>
        </div>

        {/* Estimation - Affichée uniquement sur le mesh original */}
        {currentTriangles > 0 && !isSimplifiedMesh && (
          <div style={{
            background: 'var(--v2-info-bg)',
            borderRadius: 'var(--v2-radius-lg)',
            padding: 'var(--v2-spacing-md)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--v2-spacing-xs)',
            fontSize: '0.875rem'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles actuels:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-text-primary)' }}>
                {currentTriangles.toLocaleString()}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles après simplification:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-info-text)' }}>
                ~{estimatedTriangles.toLocaleString()}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles supprimés:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-error-text)' }}>
                ~{(currentTriangles - estimatedTriangles).toLocaleString()}
              </span>
            </div>
          </div>
        )}

        {/* Options avancees */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-sm)' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-text-secondary)' }}>Options avancees</h3>

          {/* Option preserve_boundary (mode standard uniquement) */}
          {mode === 'standard' && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--v2-spacing-xs)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={preserveBoundary}
                onChange={(e) => setPreserveBoundary(e.target.checked)}
                disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
                style={{
                  width: '16px',
                  height: '16px',
                  accentColor: 'var(--v2-accent-primary)',
                  cursor: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 'not-allowed' : 'pointer',
                  opacity: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 0.5 : 1
                }}
              />
              <span style={{ fontSize: '0.875rem', color: 'var(--v2-text-secondary)' }}>
                Preserver les bords du maillage
              </span>
            </label>
          )}

          {/* Slider flat_multiplier (mode adaptatif uniquement) */}
          {mode === 'adaptive' && (
            <div>
              <label style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: 500,
                color: 'var(--v2-text-secondary)',
                marginBottom: 'var(--v2-spacing-xs)'
              }}>
                Agressivité zones plates: <span style={{ color: 'var(--v2-accent-primary)', fontWeight: 600 }}>{flatMultiplier.toFixed(1)}x</span>
              </label>
              <input
                type="range"
                min="1.0"
                max="3.0"
                step="0.1"
                value={flatMultiplier}
                onChange={(e) => setFlatMultiplier(parseFloat(e.target.value))}
                disabled={isProcessing || isGltfFormat || isSimplifiedMesh}
                style={{
                  width: '100%',
                  height: '6px',
                  background: 'var(--v2-bg-tertiary)',
                  borderRadius: 'var(--v2-radius-lg)',
                  appearance: 'none',
                  cursor: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 'not-allowed' : 'pointer',
                  opacity: (isProcessing || isGltfFormat || isSimplifiedMesh) ? 0.5 : 1,
                  accentColor: 'var(--v2-accent-primary)'
                }}
              />
              <div style={{
                fontSize: '0.75rem',
                color: 'var(--v2-text-muted)',
                marginTop: '4px'
              }}>
                Les zones plates seront simplifiées {flatMultiplier.toFixed(1)}x plus agressivement que les zones courbes
              </div>
            </div>
          )}
        </div>

        {/* Bouton de simplification */}
        <button
          type="submit"
          disabled={isProcessing || !meshInfo || isGltfFormat || isSimplifiedMesh}
          className="v2-btn v2-btn-primary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            borderRadius: 'var(--v2-radius-lg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            opacity: (isProcessing || !meshInfo || isGltfFormat || isSimplifiedMesh) ? 0.5 : 1,
            cursor: (isProcessing || !meshInfo || isGltfFormat || isSimplifiedMesh) ? 'not-allowed' : 'pointer'
          }}
        >
          {isProcessing ? (
            <>
              <svg style={{ animation: 'spin 1s linear infinite', width: '20px', height: '20px' }} fill="none" viewBox="0 0 24 24">
                <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Simplification en cours...</span>
            </>
          ) : (
            <>
              <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Lancer la simplification</span>
            </>
          )}
        </button>

        {/* Boutons de navigation entre modèles */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-xs)' }}>
          {/* Bouton pour charger le résultat simplifié */}
          {currentTask && currentTask.taskType === 'simplify' && currentTask.status === 'completed' && currentTask.result && !meshInfo?.isSimplified && (
            <button
              type="button"
              onClick={onLoadSimplified}
              className="v2-btn"
              style={{
                width: '100%',
                background: 'var(--v2-success)',
                color: '#ffffff',
                padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
                borderRadius: 'var(--v2-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--v2-spacing-xs)',
                fontWeight: 500
              }}
            >
              <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              className="v2-btn v2-btn-primary"
              style={{
                width: '100%',
                padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
                borderRadius: 'var(--v2-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--v2-spacing-xs)',
                fontWeight: 500
              }}
            >
              <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Charger le modèle original</span>
            </button>
          )}
        </div>
      </form>

      {/* Ajout du keyframes pour l'animation spin */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default SimplificationControls
