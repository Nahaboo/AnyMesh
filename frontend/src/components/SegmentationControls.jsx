import { useState } from 'react'

function SegmentationControls({ meshInfo, onSegment, onLoadSegmented, onLoadOriginal, currentTask, isProcessing }) {
  const [method, setMethod] = useState('connectivity')

  // Détection si on visualise un mesh segmenté
  const isSegmentedMesh = meshInfo?.isSegmented || false

  // Détection si le mesh est retopologisé (quads incompatibles avec segmentation)
  const isRetopologizedMesh = meshInfo?.isRetopologized || false

  // Paramètres spécifiques par méthode
  const [angleThreshold, setAngleThreshold] = useState(45)
  const [numClusters, setNumClusters] = useState(5)
  const [numPlanes, setNumPlanes] = useState(3)

  const methodDescriptions = {
    connectivity: "Détecte les parties déconnectées (anses, bracelets amovibles)",
    sharp_edges: "Segmente aux arêtes vives (fermetures, boucles, coutures)",
    curvature: "Segmente par zones de courbure similaire (plat vs arrondi)",
    planes: "Détecte les surfaces planes dominantes (faces de montre, côtés)"
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    if (onSegment && meshInfo) {
      const params = {
        filename: meshInfo.originalFilename || meshInfo.filename,
        method: method,
        is_generated: meshInfo.isGenerated || false,
        is_simplified: meshInfo.isSimplified || false,
        is_retopo: meshInfo.isRetopologized || false
      }

      // Ajouter paramètres spécifiques
      if (method === 'sharp_edges') {
        params.angle_threshold = angleThreshold
      } else if (method === 'curvature') {
        params.num_clusters = numClusters
      } else if (method === 'planes') {
        params.num_planes = numPlanes
      }

      onSegment(params)
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
        Segmentation de Maillage
      </h2>

      {/* Bandeau d'avertissement si mesh retopologisé */}
      {isRetopologizedMesh && !isSegmentedMesh && (
        <div style={{
          background: 'var(--v2-warning-bg)',
          border: '1px solid var(--v2-warning-border)',
          borderRadius: 'var(--v2-radius-md)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-lg)',
          fontSize: '0.875rem',
          color: 'var(--v2-warning-text)'
        }}>
          <strong style={{ display: 'block', marginBottom: '4px' }}>Segmentation non disponible sur mesh retopologisé</strong>
          La segmentation ne fonctionne qu'avec des meshes triangulés. Les meshes retopologisés contiennent des quads qui seraient détruits par la segmentation. Pour segmenter ce modèle, retournez au modèle original en cliquant sur "Charger le modèle original" dans le panneau de retopologie.
        </div>
      )}

      {/* Bandeau d'information si mesh segmenté affiché */}
      {isSegmentedMesh && (
        <div style={{
          background: 'var(--v2-info-bg)',
          border: '1px solid var(--v2-info-border)',
          borderRadius: 'var(--v2-radius-md)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-lg)'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--v2-spacing-sm)' }}>
            <svg style={{ width: '20px', height: '20px', flexShrink: 0, marginTop: '2px' }} fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div>
              <h3 style={{
                fontSize: '0.875rem',
                fontWeight: 600,
                color: 'var(--v2-info-text)',
                marginBottom: 'var(--v2-spacing-xs)'
              }}>
                Modèle segmenté affiché
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--v2-info-text)' }}>
                Vous visualisez le résultat de la segmentation. Pour effectuer une nouvelle segmentation, retournez au modèle original.
              </p>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-lg)' }}>

        {/* Sélecteur de méthode */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)',
            marginBottom: 'var(--v2-spacing-sm)'
          }}>
            Méthode de segmentation
          </label>

          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            disabled={isProcessing || isSegmentedMesh || isRetopologizedMesh}
            style={{
              width: '100%',
              padding: 'var(--v2-spacing-sm)',
              borderRadius: 'var(--v2-radius-md)',
              border: '1px solid var(--v2-border-color)',
              background: 'var(--v2-bg-primary)',
              color: 'var(--v2-text-primary)',
              fontSize: '0.875rem',
              cursor: (isProcessing || isRetopologizedMesh) ? 'not-allowed' : 'pointer'
            }}
          >
            <option value="connectivity">Connexité (parties détachées)</option>
            <option value="sharp_edges">Arêtes vives (frontières)</option>
            <option value="curvature">Courbure (plat vs arrondi)</option>
            <option value="planes">Plans dominants (surfaces plates)</option>
          </select>

          <p style={{
            fontSize: '0.75rem',
            color: 'var(--v2-text-muted)',
            marginTop: 'var(--v2-spacing-xs)'
          }}>
            {methodDescriptions[method]}
          </p>
        </div>

        {/* Paramètres spécifiques selon méthode */}
        {method === 'sharp_edges' && (
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-xs)'
            }}>
              Seuil d'angle (degrés): <span style={{ color: 'var(--v2-accent-primary)' }}>{angleThreshold}°</span>
            </label>
            <input
              type="range"
              min="10"
              max="90"
              step="5"
              value={angleThreshold}
              onChange={(e) => setAngleThreshold(parseInt(e.target.value))}
              disabled={isProcessing || isRetopologizedMesh}
              style={{
                width: '100%',
                accentColor: 'var(--v2-accent-primary)'
              }}
            />
          </div>
        )}

        {method === 'curvature' && (
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-xs)'
            }}>
              Nombre de segments: <span style={{ color: 'var(--v2-accent-primary)' }}>{numClusters}</span>
            </label>
            <input
              type="range"
              min="2"
              max="10"
              step="1"
              value={numClusters}
              onChange={(e) => setNumClusters(parseInt(e.target.value))}
              disabled={isProcessing || isRetopologizedMesh}
              style={{
                width: '100%',
                accentColor: 'var(--v2-accent-primary)'
              }}
            />
            <p style={{
              fontSize: '0.75rem',
              color: 'var(--v2-text-muted)',
              marginTop: 'var(--v2-spacing-xs)'
            }}>
              Nombre de zones de courbure différentes à détecter. Augmenter pour plus de détails, diminuer pour regrouper les zones similaires.
            </p>
          </div>
        )}

        {method === 'planes' && (
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-xs)'
            }}>
              Nombre de plans: <span style={{ color: 'var(--v2-accent-primary)' }}>{numPlanes}</span>
            </label>
            <input
              type="range"
              min="1"
              max="6"
              step="1"
              value={numPlanes}
              onChange={(e) => setNumPlanes(parseInt(e.target.value))}
              disabled={isProcessing || isRetopologizedMesh}
              style={{
                width: '100%',
                accentColor: 'var(--v2-accent-primary)'
              }}
            />
            <p style={{
              fontSize: '0.75rem',
              color: 'var(--v2-text-muted)',
              marginTop: 'var(--v2-spacing-xs)'
            }}>
              Nombre maximum de surfaces planes principales à isoler. Augmenter pour détecter plus de faces (idéal pour objets géométriques complexes).
            </p>
          </div>
        )}

        {/* Bouton de segmentation */}
        <button
          type="submit"
          disabled={isProcessing || !meshInfo || isSegmentedMesh || isRetopologizedMesh}
          className="v2-btn v2-btn-primary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            opacity: (isProcessing || !meshInfo || isSegmentedMesh || isRetopologizedMesh) ? 0.5 : 1,
            cursor: (isProcessing || !meshInfo || isSegmentedMesh || isRetopologizedMesh) ? 'not-allowed' : 'pointer'
          }}
        >
          {isProcessing ? 'Segmentation en cours...' : 'Lancer la segmentation'}
        </button>

        {/* Bouton pour charger résultat */}
        {currentTask && currentTask.taskType === 'segment' && currentTask.status === 'completed' && !isSegmentedMesh && (
          <button
            type="button"
            onClick={onLoadSegmented}
            className="v2-btn"
            style={{
              width: '100%',
              background: 'var(--v2-success)',
              color: '#ffffff'
            }}
          >
            Charger le résultat segmenté
          </button>
        )}

        {/* Bouton pour recharger le modèle original */}
        {isSegmentedMesh && onLoadOriginal && (
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
              gap: 'var(--v2-spacing-sm)',
              fontSize: '0.875rem',
              fontWeight: 500
            }}
          >
            <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Charger le modèle original</span>
          </button>
        )}
      </form>
    </div>
  )
}

export default SegmentationControls
