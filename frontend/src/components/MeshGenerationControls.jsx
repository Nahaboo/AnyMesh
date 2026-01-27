import { useState } from 'react'

function MeshGenerationControls({ sessionInfo, onGenerate, isProcessing }) {
  const [resolution, setResolution] = useState('medium')
  const [remeshOption, setRemeshOption] = useState('quad')
  const [provider, setProvider] = useState('stability')

  const handleGenerate = () => {
    if (onGenerate) {
      onGenerate({
        sessionId: sessionInfo.sessionId,
        resolution,
        remeshOption,
        provider
      })
    }
  }

  // Informations des providers
  const providerInfo = {
    stability: {
      name: 'Stability AI',
      description: 'API cloud, haute qualite',
      time: { low: '10-30 sec', medium: '30-60 sec', high: '1-3 min' }
    },
    triposr: {
      name: 'TripoSR (Local)',
      description: 'Gratuit, necessite GPU',
      time: { low: '< 5 sec', medium: '< 10 sec', high: '< 30 sec' }
    }
  }

  // Temps estime selon provider et resolution
  const estimatedTime = providerInfo[provider].time[resolution]

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
        Générer un modèle 3D
      </h2>

      {/* Informations de session */}
      {sessionInfo && (
        <div style={{
          marginBottom: 'var(--v2-spacing-lg)',
          padding: 'var(--v2-spacing-md)',
          background: 'var(--v2-info-bg)',
          borderRadius: 'var(--v2-radius-lg)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--v2-spacing-xs)', fontSize: '0.875rem', color: 'var(--v2-info-text)' }}>
            <svg style={{ width: '20px', height: '20px' }} fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
                clipRule="evenodd"
              />
            </svg>
            <span style={{ fontWeight: 500 }}>
              {sessionInfo.imagesCount} image(s) prête(s) pour la génération
            </span>
          </div>
        </div>
      )}

      {/* Contrôles de génération */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
        {/* Résolution */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)',
            marginBottom: 'var(--v2-spacing-xs)'
          }}>
            Résolution du maillage
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--v2-spacing-xs)' }}>
            {['low', 'medium', 'high'].map((res) => (
              <button
                key={res}
                onClick={() => setResolution(res)}
                disabled={isProcessing}
                style={{
                  padding: 'var(--v2-spacing-xs) var(--v2-spacing-sm)',
                  borderRadius: 'var(--v2-radius-lg)',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  transition: 'all var(--v2-transition-base)',
                  background: resolution === res ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
                  color: resolution === res ? '#ffffff' : 'var(--v2-text-secondary)',
                  border: 'none',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  opacity: isProcessing ? 0.5 : 1
                }}
              >
                {res === 'low' && 'Basse'}
                {res === 'medium' && 'Moyenne'}
                {res === 'high' && 'Haute'}
              </button>
            ))}
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)', marginTop: 'var(--v2-spacing-xs)' }}>
            Temps estime: {estimatedTime}
          </p>
        </div>

        {/* Selecteur de Provider */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)',
            marginBottom: 'var(--v2-spacing-xs)'
          }}>
            Moteur de generation
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--v2-spacing-xs)' }}>
            {['stability', 'triposr'].map((p) => (
              <button
                key={p}
                onClick={() => setProvider(p)}
                disabled={isProcessing}
                style={{
                  padding: 'var(--v2-spacing-sm)',
                  borderRadius: 'var(--v2-radius-lg)',
                  fontSize: '0.875rem',
                  transition: 'all var(--v2-transition-base)',
                  background: provider === p ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
                  color: provider === p ? '#ffffff' : 'var(--v2-text-secondary)',
                  border: 'none',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  opacity: isProcessing ? 0.5 : 1,
                  textAlign: 'left'
                }}
              >
                <div style={{ fontWeight: 500 }}>{providerInfo[p].name}</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.8, marginTop: '2px' }}>
                  {providerInfo[p].description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Topologie du mesh (Remesh Option) - Stability AI uniquement */}
        {provider === 'stability' && (
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-xs)'
            }}>
              Topologie du mesh
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--v2-spacing-xs)' }}>
              {[
                { value: 'none', label: 'Aucune' },
                { value: 'triangle', label: 'Triangle' },
                { value: 'quad', label: 'Quad' }
              ].map((option) => (
                <button
                  key={option.value}
                  onClick={() => setRemeshOption(option.value)}
                  disabled={isProcessing}
                  style={{
                    padding: 'var(--v2-spacing-xs) var(--v2-spacing-sm)',
                    borderRadius: 'var(--v2-radius-lg)',
                    fontSize: '0.875rem',
                    fontWeight: 500,
                    transition: 'all var(--v2-transition-base)',
                    background: remeshOption === option.value ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
                    color: remeshOption === option.value ? '#ffffff' : 'var(--v2-text-secondary)',
                    border: 'none',
                    cursor: isProcessing ? 'not-allowed' : 'pointer',
                    opacity: isProcessing ? 0.5 : 1
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)', marginTop: 'var(--v2-spacing-xs)' }}>
              {remeshOption === 'none' && 'Pas de remaillage (plus rapide, topologie basique)'}
              {remeshOption === 'triangle' && 'Triangles optimises (bonne qualite)'}
              {remeshOption === 'quad' && 'Quadrilateres (meilleure qualite, recommande)'}
            </p>
          </div>
        )}

        {/* Bouton de génération */}
        <button
          onClick={handleGenerate}
          disabled={isProcessing || !sessionInfo}
          className="v2-btn"
          style={{
            width: '100%',
            background: 'var(--v2-accent-primary)',
            color: '#ffffff',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            borderRadius: 'var(--v2-radius-lg)',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            cursor: (isProcessing || !sessionInfo) ? 'not-allowed' : 'pointer',
            opacity: (isProcessing || !sessionInfo) ? 0.5 : 1
          }}
        >
          {isProcessing ? (
            <>
              <svg style={{ animation: 'spin 1s linear infinite', width: '20px', height: '20px' }} fill="none" viewBox="0 0 24 24">
                <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  style={{ opacity: 0.75 }}
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span>Génération en cours...</span>
            </>
          ) : (
            <>
              <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

export default MeshGenerationControls
