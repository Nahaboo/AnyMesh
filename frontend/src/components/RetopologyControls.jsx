import { useState } from 'react'

function RetopologyControls({ meshInfo, onRetopologize, onLoadRetopologized, onLoadOriginal, currentTask, isProcessing }) {
  // Calculer le range dynamique basé sur le nombre de faces original
  // Range: [original * 2 : original * 5]
  const currentFaces = meshInfo?.triangles_count || meshInfo?.faces_count || 0
  const minFaces = currentFaces * 2
  const maxFaces = currentFaces * 5
  const defaultFaces = Math.floor((minFaces + maxFaces) / 2)

  const [targetFaceCount, setTargetFaceCount] = useState(defaultFaces)
  const [deterministic, setDeterministic] = useState(true)
  const [preserveBoundaries, setPreserveBoundaries] = useState(true)

  const isGenerated = meshInfo?.isGenerated === true

  // Vérifier si on visualise un mesh déjà retopologisé
  const isRetopologizedMesh = meshInfo?.isRetopologized === true

  const handleSubmit = (e) => {
    e.preventDefault()

    if (onRetopologize) {
      // Validation: s'assurer que currentFaces est valide
      if (!currentFaces || currentFaces <= 0) {
        console.error('[RetopologyControls] Invalid currentFaces:', currentFaces)
        console.error('[RetopologyControls] meshInfo:', meshInfo)
        alert('Erreur: Le nombre de faces du mesh est invalide. Veuillez recharger le mesh.')
        return
      }

      // Utiliser originalFilename pour la retopologie (fichier source, pas GLB)
      const filenameForRetopology = meshInfo.originalFilename || meshInfo.filename
      const isSimplified = meshInfo.isSimplified === true
      console.log('[DEBUG] Retopologie du fichier:', filenameForRetopology)
      console.log('[DEBUG] Current faces:', currentFaces)
      console.log('[DEBUG] Target faces:', targetFaceCount)
      console.log('[DEBUG] Is generated mesh:', isGenerated)
      console.log('[DEBUG] Is simplified mesh:', isSimplified)

      onRetopologize({
        filename: filenameForRetopology,
        target_face_count: targetFaceCount,
        original_face_count: currentFaces,  // Envoyer le nombre de faces original
        deterministic: deterministic,
        preserve_boundaries: preserveBoundaries,
        is_generated: isGenerated,  // Indiquer si c'est un mesh généré
        is_simplified: isSimplified  // Indiquer si c'est un mesh simplifié
      })
    }
  }

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
        Parametres de retopologie
      </h2>

      {/* Avertissement si mesh déjà retopologisé */}
      {isRetopologizedMesh && (
        <div style={{
          background: 'var(--v2-warning-bg)',
          border: '1px solid var(--v2-warning-border)',
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-md)',
          fontSize: '0.875rem',
          color: 'var(--v2-warning-text)'
        }}>
          <strong style={{ display: 'block', marginBottom: '4px' }}>Mesh déjà retopologisé</strong>
          Ce mesh a déjà été retopologisé. Pour effectuer une nouvelle retopologie, chargez d'abord le modèle original.
        </div>
      )}

      {/* Info retopologie */}
      <div style={{
        background: 'var(--v2-info-bg)',
        border: '1px solid var(--v2-info-border)',
        borderRadius: 'var(--v2-radius-lg)',
        padding: 'var(--v2-spacing-md)',
        marginBottom: 'var(--v2-spacing-md)',
        fontSize: '0.875rem',
        color: 'var(--v2-info-text)'
      }}>
        <strong style={{ display: 'block', marginBottom: '4px' }}>Qu'est-ce que la retopologie ?</strong>
        Recrée un mesh avec une topologie optimisée (triangles uniformes ou quads). Idéal pour l'animation, la subdivision ou l'alignement aux features géométriques.
      </div>

      <form onSubmit={handleSubmit}>
        {/* Slider Target Face Count */}
        <div style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 'var(--v2-spacing-sm)'
          }}>
            <label style={{
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--v2-text-primary)'
            }}>
              Nombre de faces cibles
            </label>
            <span style={{
              fontSize: '0.875rem',
              fontWeight: 600,
              color: 'var(--v2-accent-primary)',
              background: 'var(--v2-bg-tertiary)',
              padding: '4px 12px',
              borderRadius: 'var(--v2-radius-md)'
            }}>
              {targetFaceCount.toLocaleString()}
            </span>
          </div>

          <input
            type="range"
            min={minFaces}
            max={maxFaces}
            step={Math.max(100, Math.floor((maxFaces - minFaces) / 100))}
            value={targetFaceCount}
            onChange={(e) => setTargetFaceCount(parseInt(e.target.value))}
            disabled={isProcessing || isRetopologizedMesh}
            style={{
              width: '100%',
              accentColor: 'var(--v2-accent-primary)',
              cursor: (isProcessing || isRetopologizedMesh) ? 'not-allowed' : 'pointer',
              opacity: (isProcessing || isRetopologizedMesh) ? 0.5 : 1
            }}
          />

          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: '4px',
            fontSize: '0.75rem',
            color: 'var(--v2-text-tertiary)'
          }}>
            <span>{(minFaces / 1000).toFixed(0)}k</span>
            <span style={{ color: 'var(--v2-text-secondary)' }}>
              Original: {(currentFaces / 1000).toFixed(0)}k
            </span>
            <span>{(maxFaces / 1000).toFixed(0)}k</span>
          </div>
        </div>

        {/* Estimation */}
        {currentFaces > 0 && (
          <div style={{
            background: 'var(--v2-bg-tertiary)',
            borderRadius: 'var(--v2-radius-lg)',
            padding: 'var(--v2-spacing-md)',
            marginBottom: 'var(--v2-spacing-lg)',
            fontSize: '0.875rem'
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: '8px'
            }}>
              <span style={{ color: 'var(--v2-text-secondary)' }}>Faces actuelles:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-text-primary)' }}>
                {currentFaces.toLocaleString()}
              </span>
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between'
            }}>
              <span style={{ color: 'var(--v2-text-secondary)' }}>Faces après retopo:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-accent-primary)' }}>
                ~{targetFaceCount.toLocaleString()}
              </span>
            </div>
            <div style={{
              fontSize: '0.75rem',
              color: 'var(--v2-text-muted)',
              marginTop: 'var(--v2-spacing-xs)',
              fontStyle: 'italic'
            }}>
              ⚠️ Le nombre final peut varier en fonction de la géométrie du mesh
            </div>
          </div>
        )}

        {/* Options */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--v2-spacing-sm)',
          marginBottom: 'var(--v2-spacing-lg)'
        }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--v2-spacing-sm)',
            fontSize: '0.875rem',
            color: 'var(--v2-text-primary)',
            cursor: (isProcessing || isRetopologizedMesh) ? 'not-allowed' : 'pointer',
            opacity: (isProcessing || isRetopologizedMesh) ? 0.5 : 1
          }}>
            <input
              type="checkbox"
              checked={deterministic}
              onChange={(e) => setDeterministic(e.target.checked)}
              disabled={isProcessing || isRetopologizedMesh}
              style={{
                width: '16px',
                height: '16px',
                accentColor: 'var(--v2-accent-primary)',
                cursor: (isProcessing || isRetopologizedMesh) ? 'not-allowed' : 'pointer'
              }}
            />
            Mode déterministe (résultats reproductibles)
          </label>

          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--v2-spacing-sm)',
            fontSize: '0.875rem',
            color: 'var(--v2-text-primary)',
            cursor: (isProcessing || isRetopologizedMesh) ? 'not-allowed' : 'pointer',
            opacity: (isProcessing || isRetopologizedMesh) ? 0.5 : 1
          }}>
            <input
              type="checkbox"
              checked={preserveBoundaries}
              onChange={(e) => setPreserveBoundaries(e.target.checked)}
              disabled={isProcessing || isRetopologizedMesh}
              style={{
                width: '16px',
                height: '16px',
                accentColor: 'var(--v2-accent-primary)',
                cursor: (isProcessing || isRetopologizedMesh) ? 'not-allowed' : 'pointer'
              }}
            />
            Préserver les bordures (meshes ouverts)
          </label>
        </div>

        {/* Bouton Lancer */}
        <button
          type="submit"
          disabled={isProcessing || isRetopologizedMesh || !meshInfo}
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-md)',
            background: (isProcessing || isRetopologizedMesh || !meshInfo)
              ? 'var(--v2-bg-tertiary)'
              : 'var(--v2-accent-primary)',
            color: (isProcessing || isRetopologizedMesh || !meshInfo)
              ? 'var(--v2-text-tertiary)'
              : '#ffffff',
            border: 'none',
            borderRadius: 'var(--v2-radius-lg)',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: (isProcessing || isRetopologizedMesh || !meshInfo) ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            boxShadow: (isProcessing || isRetopologizedMesh || !meshInfo)
              ? 'none'
              : 'var(--v2-shadow-md)',
            marginBottom: 'var(--v2-spacing-md)'
          }}
        >
          {isProcessing ? 'Retopologie en cours...' : 'Lancer la retopologie'}
        </button>

        {/* Task status */}
        {currentTask && currentTask.taskType === 'retopology' && currentTask.status === 'processing' && (
          <div style={{
            background: 'var(--v2-info-bg)',
            border: '1px solid var(--v2-info-border)',
            borderRadius: 'var(--v2-radius-lg)',
            padding: 'var(--v2-spacing-md)',
            marginBottom: 'var(--v2-spacing-md)',
            fontSize: '0.875rem',
            color: 'var(--v2-info-text)'
          }}>
            <div style={{ marginBottom: '8px' }}>
              <strong>Retopologie en cours...</strong>
            </div>
            <div style={{
              fontSize: '0.8rem',
              color: 'var(--v2-text-tertiary)'
            }}>
              Cela peut prendre quelques secondes selon la taille du mesh.
            </div>
          </div>
        )}

        {/* Task completed */}
        {currentTask && currentTask.taskType === 'retopology' && currentTask.status === 'completed' && (
          <div style={{
            background: 'var(--v2-success-bg)',
            border: '1px solid var(--v2-success-border)',
            borderRadius: 'var(--v2-radius-lg)',
            padding: 'var(--v2-spacing-md)',
            marginBottom: 'var(--v2-spacing-md)',
            fontSize: '0.875rem',
            color: 'var(--v2-success-text)'
          }}>
            <strong style={{ display: 'block', marginBottom: '8px' }}>
              ✓ Retopologie terminée !
            </strong>
            {currentTask.result && (
              <div style={{ fontSize: '0.8rem' }}>
                <div>
                  Original: {currentTask.result.original?.vertices?.toLocaleString()} vertices, {currentTask.result.original?.faces?.toLocaleString()} faces
                </div>
                <div style={{ color: 'var(--v2-accent-primary)', fontWeight: 600 }}>
                  Résultat: {currentTask.result.vertices_count?.toLocaleString()} vertices, {currentTask.result.faces_count?.toLocaleString()} faces
                </div>
              </div>
            )}
          </div>
        )}

        {/* Task failed */}
        {currentTask && currentTask.taskType === 'retopology' && currentTask.status === 'failed' && (
          <div style={{
            background: 'var(--v2-error-bg)',
            border: '1px solid var(--v2-error-border)',
            borderRadius: 'var(--v2-radius-lg)',
            padding: 'var(--v2-spacing-md)',
            marginBottom: 'var(--v2-spacing-md)',
            fontSize: '0.875rem',
            color: 'var(--v2-error-text)'
          }}>
            <strong style={{ display: 'block', marginBottom: '4px' }}>
              ✗ Erreur lors de la retopologie
            </strong>
            {currentTask.error || 'Une erreur est survenue'}
          </div>
        )}

        {/* Boutons de navigation entre modèles */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-xs)' }}>
          {/* Bouton pour charger le résultat retopologisé */}
          {currentTask && currentTask.taskType === 'retopology' && currentTask.status === 'completed' && currentTask.result && !meshInfo?.isRetopologized && (
            <button
              type="button"
              onClick={onLoadRetopologized}
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
              <span>Charger le résultat retopologisé</span>
            </button>
          )}

          {/* Bouton pour recharger le modèle original */}
          {meshInfo?.isRetopologized && (
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
    </div>
  )
}

export default RetopologyControls
