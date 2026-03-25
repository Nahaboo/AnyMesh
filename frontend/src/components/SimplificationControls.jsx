import { useState } from 'react'

function SimplificationControls({ meshInfo, initialMeshInfo, onSimplify, onLoadSimplified, onLoadOriginal, onCompare, onLoadCompared, currentTask, isProcessing }) {
  const [simplificationLevel, setSimplificationLevel] = useState(1)
  const [isComparing, setIsComparing] = useState(false)
  const [preserveTexture, setPreserveTexture] = useState(false)

  const levelToRatio = {
    0: 0.3,
    1: 0.5,
    2: 0.8
  }

  const levelLabels = ['Basse', 'Moyenne', 'Forte']
  const reductionRatio = levelToRatio[simplificationLevel]

  const isGenerated = meshInfo?.isGenerated === true
  const isSimplifiedMesh = meshInfo?.isSimplified === true
  const isRetopologizedMesh = false
  const hasTexture = meshInfo?.has_textures === true || isGenerated

  const handleSubmit = (e) => {
    e.preventDefault()
    if (onSimplify) {
      const filenameForSimplification = meshInfo.originalFilename || meshInfo.filename
      onSimplify({
        mode: 'standard',
        filename: filenameForSimplification,
        reduction_ratio: reductionRatio,
        is_generated: isGenerated,
        preserve_texture: hasTexture && preserveTexture
      })
    }
  }

  const currentTriangles = meshInfo?.triangles_count || meshInfo?.faces_count || 0
  const estimatedTriangles = currentTriangles > 0
    ? Math.round(currentTriangles * (1 - reductionRatio))
    : 0

  // Compare logic
  const simplifyTaskCompleted = currentTask?.taskType === 'simplify' &&
    currentTask?.status === 'completed' && currentTask?.result?.success

  const compareTaskCompleted = currentTask?.taskType === 'compare' &&
    currentTask?.status === 'completed' && currentTask?.result?.success

  const compareStats = compareTaskCompleted ? currentTask.result.stats : (meshInfo?.compareStats || null)

  const compareTaskBusy = currentTask?.taskType === 'compare' && currentTask?.status === 'processing'

  const handleCompare = () => {
    if (!meshInfo || !initialMeshInfo) return
    setIsComparing(true)
    onCompare({
      filenameRef: initialMeshInfo.filename,
      filenameComp: meshInfo.filename,
      isGeneratedRef: initialMeshInfo.isGenerated || false,
      isSimplifiedRef: false,
      isGeneratedComp: meshInfo.isGenerated || false,
      isSimplifiedComp: meshInfo.isSimplified || false,
      isRetopolComp: meshInfo.isRetopologized || false,
    })
  }

  const handleLoadHeatmap = () => {
    onLoadCompared()
    setIsComparing(false)
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
        Parametres de simplification
      </h2>

      {/* Texture options */}
      {hasTexture && !isSimplifiedMesh && !isRetopologizedMesh && (
        <div style={{ marginBottom: 'var(--v2-spacing-md)' }}>
          {!preserveTexture && (
            <div style={{
              background: 'var(--v2-warning-bg)',
              border: '1px solid var(--v2-warning-border)',
              borderRadius: 'var(--v2-radius-lg)',
              padding: 'var(--v2-spacing-md)',
              marginBottom: 'var(--v2-spacing-sm)'
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--v2-spacing-sm)' }}>
                <svg style={{ width: '20px', height: '20px', color: 'var(--v2-warning-text)', marginTop: '2px', flexShrink: 0 }} fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-warning-text)', marginBottom: '4px' }}>
                    Textures seront perdues
                  </h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--v2-warning-text)' }}>
                    La simplification modifie la geometrie. Les textures et materiaux ne seront pas conserves.
                  </p>
                </div>
              </div>
            </div>
          )}
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--v2-spacing-sm)',
            cursor: 'pointer',
            fontSize: '0.875rem',
            color: 'var(--v2-text-secondary)',
            userSelect: 'none'
          }}>
            <input
              type="checkbox"
              checked={preserveTexture}
              onChange={(e) => setPreserveTexture(e.target.checked)}
              style={{ accentColor: 'var(--v2-accent-primary)', width: '16px', height: '16px', cursor: 'pointer' }}
            />
            Conserver la texture (transfert UV)
          </label>
        </div>
      )}

      {/* Warning: already simplified */}
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
                Modele simplifie affiche
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--v2-info-text)' }}>
                Vous visualisez actuellement le modele simplifie. Pour effectuer une nouvelle simplification, retournez d'abord au modele original.
              </p>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-lg)' }}>
        {/* Slider */}
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
            disabled={isProcessing || isSimplifiedMesh || isRetopologizedMesh}
            style={{
              width: '100%',
              height: '8px',
              background: 'var(--v2-bg-tertiary)',
              borderRadius: 'var(--v2-radius-lg)',
              appearance: 'none',
              cursor: (isProcessing || isSimplifiedMesh || isRetopologizedMesh) ? 'not-allowed' : 'pointer',
              opacity: (isProcessing || isSimplifiedMesh || isRetopologizedMesh) ? 0.5 : 1,
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
            {simplificationLevel === 0 && "Garde 70% des triangles (qualite elevee)"}
            {simplificationLevel === 1 && "Garde 50% des triangles (equilibre)"}
            {simplificationLevel === 2 && "Garde 20% des triangles (fichier leger)"}
          </div>
        </div>

        {/* Estimation */}
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
              <span style={{ fontWeight: 600, color: 'var(--v2-text-primary)' }}>{currentTriangles.toLocaleString()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles apres simplification:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-info-text)' }}>~{estimatedTriangles.toLocaleString()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles supprimes:</span>
              <span style={{ fontWeight: 600, color: 'var(--v2-error-text)' }}>~{(currentTriangles - estimatedTriangles).toLocaleString()}</span>
            </div>
          </div>
        )}

        {/* Simplify button */}
        <button
          type="submit"
          disabled={isProcessing || !meshInfo || isSimplifiedMesh || isRetopologizedMesh}
          className="v2-btn v2-btn-primary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            borderRadius: 'var(--v2-radius-lg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            opacity: (isProcessing || !meshInfo || isSimplifiedMesh || isRetopologizedMesh) ? 0.5 : 1,
            cursor: (isProcessing || !meshInfo || isSimplifiedMesh || isRetopologizedMesh) ? 'not-allowed' : 'pointer'
          }}
        >
          {isProcessing && currentTask?.taskType === 'simplify' ? (
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

        {/* Navigation buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-xs)' }}>
          {simplifyTaskCompleted && !meshInfo?.isSimplified && (
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
              <span>Charger le resultat simplifie</span>
            </button>
          )}

          {(meshInfo?.isSimplified || meshInfo?.isCompared) && (
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
              <span>Charger le modele original</span>
            </button>
          )}
        </div>
      </form>

      {/* Compare section - only shown after simplification is loaded */}
      {meshInfo?.isSimplified && initialMeshInfo && (
        <div style={{
          marginTop: 'var(--v2-spacing-lg)',
          paddingTop: 'var(--v2-spacing-lg)',
          borderTop: '1px solid var(--v2-border-secondary)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--v2-spacing-md)'
        }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--v2-text-secondary)' }}>
            Ecart geometrique
          </div>

          {/* Compare button */}
          {!meshInfo?.isCompared && (
            <button
              onClick={handleCompare}
              disabled={compareTaskBusy}
              className="v2-btn"
              style={{
                width: '100%',
                background: compareTaskBusy ? 'var(--v2-bg-tertiary)' : 'var(--v2-accent-primary)',
                color: compareTaskBusy ? 'var(--v2-text-muted)' : '#ffffff',
                padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
                borderRadius: 'var(--v2-radius-lg)',
                fontWeight: 500,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--v2-spacing-xs)',
                cursor: compareTaskBusy ? 'not-allowed' : 'pointer',
                border: 'none'
              }}
            >
              {compareTaskBusy ? (
                <>
                  <svg style={{ animation: 'spin 1s linear infinite', width: '18px', height: '18px' }} fill="none" viewBox="0 0 24 24">
                    <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Calcul en cours...</span>
                </>
              ) : (
                <>
                  <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>Analyser l'ecart avec l'original</span>
                </>
              )}
            </button>
          )}

          {/* Load heatmap */}
          {compareTaskCompleted && !meshInfo?.isCompared && (
            <button
              onClick={handleLoadHeatmap}
              className="v2-btn v2-btn-secondary"
              style={{
                width: '100%',
                padding: 'var(--v2-spacing-sm)',
                borderRadius: 'var(--v2-radius-lg)',
                fontWeight: 500,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--v2-spacing-xs)'
              }}
            >
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              Voir la heatmap
            </button>
          )}

          {/* Back to mesh from heatmap */}
          {meshInfo?.isCompared && (
            <button
              onClick={onLoadOriginal}
              className="v2-btn v2-btn-secondary"
              style={{
                width: '100%',
                padding: 'var(--v2-spacing-sm)',
                borderRadius: 'var(--v2-radius-lg)',
                fontWeight: 500
              }}
            >
              Retour au mesh simplifie
            </button>
          )}

          {/* Stats */}
          {compareStats && (
            <div style={{
              padding: 'var(--v2-spacing-md)',
              background: 'var(--v2-bg-tertiary)',
              borderRadius: 'var(--v2-radius-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--v2-spacing-sm)'
            }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--v2-text-secondary)' }}>
                Statistiques de distance
              </div>
              {[
                { label: 'Hausdorff (max)', value: `${compareStats.hausdorff_pct}%` },
                { label: 'Distance moyenne', value: `${compareStats.mean_pct}%` },
                { label: 'RMS', value: compareStats.rms?.toFixed(6) },
                { label: 'P95', value: compareStats.p95?.toFixed(6) },
              ].map(({ label, value }) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                  <span style={{ color: 'var(--v2-text-secondary)' }}>{label}</span>
                  <span style={{ color: 'var(--v2-text-primary)', fontWeight: 500, fontFamily: 'monospace' }}>{value}</span>
                </div>
              ))}
              <div style={{ marginTop: 'var(--v2-spacing-xs)' }}>
                <div style={{ fontSize: '0.6875rem', color: 'var(--v2-text-muted)', marginBottom: '4px' }}>Legende</div>
                <div style={{
                  height: '12px',
                  borderRadius: '6px',
                  background: 'linear-gradient(to right, #0000ff, #00ffff, #00ff00, #ffff00, #ff0000)'
                }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.625rem', color: 'var(--v2-text-muted)', marginTop: '2px' }}>
                  <span>Identique</span>
                  <span>Ecart max</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

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
