import { useState } from 'react'

function SegmentationControls({ meshInfo, onSegment, onLoadSegmented, currentTask, isProcessing }) {
  const [method, setMethod] = useState('connectivity')

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
        method: method
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
            disabled={isProcessing}
            style={{
              width: '100%',
              padding: 'var(--v2-spacing-sm)',
              borderRadius: 'var(--v2-radius-md)',
              border: '1px solid var(--v2-border-color)',
              background: 'var(--v2-bg-primary)',
              color: 'var(--v2-text-primary)',
              fontSize: '0.875rem',
              cursor: isProcessing ? 'not-allowed' : 'pointer'
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
              disabled={isProcessing}
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
              disabled={isProcessing}
              style={{
                width: '100%',
                accentColor: 'var(--v2-accent-primary)'
              }}
            />
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
              disabled={isProcessing}
              style={{
                width: '100%',
                accentColor: 'var(--v2-accent-primary)'
              }}
            />
          </div>
        )}

        {/* Bouton de segmentation */}
        <button
          type="submit"
          disabled={isProcessing || !meshInfo}
          className="v2-btn v2-btn-primary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            opacity: (isProcessing || !meshInfo) ? 0.5 : 1,
            cursor: (isProcessing || !meshInfo) ? 'not-allowed' : 'pointer'
          }}
        >
          {isProcessing ? 'Segmentation en cours...' : 'Lancer la segmentation'}
        </button>

        {/* Bouton pour charger résultat */}
        {currentTask && currentTask.taskType === 'segment' && currentTask.status === 'completed' && (
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
      </form>
    </div>
  )
}

export default SegmentationControls
