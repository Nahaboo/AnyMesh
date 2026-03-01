import { useState } from 'react'

/**
 * CompareControls - UI for mesh comparison (heatmap diff)
 * Compares current mesh with original to show geometric differences.
 */
function CompareControls({ meshInfo, initialMeshInfo, onCompare, onLoadCompared, onLoadOriginal, currentTask, isProcessing }) {
  const [isComparing, setIsComparing] = useState(false)

  const canCompare = meshInfo && initialMeshInfo &&
    meshInfo.filename !== initialMeshInfo.filename &&
    (meshInfo.isSimplified || meshInfo.isRetopologized)

  const taskCompleted = currentTask?.taskType === 'compare' &&
    currentTask?.status === 'completed' && currentTask?.result?.success

  const stats = taskCompleted ? currentTask.result.stats : (meshInfo?.compareStats || null)

  const handleCompareWithOriginal = () => {
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

  const busy = isProcessing || (currentTask?.taskType === 'compare' && currentTask?.status === 'processing')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
      {/* Info */}
      <div style={{
        fontSize: '0.8125rem',
        color: 'var(--v2-text-secondary)',
        lineHeight: 1.5
      }}>
        Compare le mesh actuel avec l'original pour visualiser les differences geometriques (heatmap).
      </div>

      {/* Current mesh info */}
      {meshInfo && (
        <div style={{
          padding: 'var(--v2-spacing-sm)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-sm)',
          fontSize: '0.75rem'
        }}>
          <div style={{ color: 'var(--v2-text-secondary)', marginBottom: '4px' }}>Mesh actuel</div>
          <div style={{ color: 'var(--v2-text-primary)', fontWeight: 500 }}>
            {meshInfo.displayFilename || meshInfo.filename}
          </div>
          <div style={{ color: 'var(--v2-text-muted)', marginTop: '2px' }}>
            {(meshInfo.faces_count || 0).toLocaleString()} faces / {(meshInfo.vertices_count || 0).toLocaleString()} vertices
          </div>
          {meshInfo.isSimplified && <span style={{ color: 'var(--v2-accent-primary)', fontSize: '0.6875rem' }}>Simplifie</span>}
          {meshInfo.isRetopologized && <span style={{ color: 'var(--v2-accent-primary)', fontSize: '0.6875rem' }}>Retopologise</span>}
        </div>
      )}

      {/* Reference mesh info */}
      {initialMeshInfo && (
        <div style={{
          padding: 'var(--v2-spacing-sm)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-sm)',
          fontSize: '0.75rem'
        }}>
          <div style={{ color: 'var(--v2-text-secondary)', marginBottom: '4px' }}>Reference (original)</div>
          <div style={{ color: 'var(--v2-text-primary)', fontWeight: 500 }}>
            {initialMeshInfo.filename}
          </div>
          <div style={{ color: 'var(--v2-text-muted)', marginTop: '2px' }}>
            {(initialMeshInfo.faces_count || initialMeshInfo.triangles_count || 0).toLocaleString()} faces / {(initialMeshInfo.vertices_count || 0).toLocaleString()} vertices
          </div>
        </div>
      )}

      {/* Compare button */}
      <button
        onClick={handleCompareWithOriginal}
        disabled={!canCompare || busy}
        className="v2-btn"
        style={{
          width: '100%',
          background: canCompare && !busy ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
          color: canCompare && !busy ? '#ffffff' : 'var(--v2-text-muted)',
          padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
          borderRadius: 'var(--v2-radius-lg)',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--v2-spacing-xs)',
          cursor: canCompare && !busy ? 'pointer' : 'not-allowed',
          border: 'none'
        }}
      >
        {busy ? (
          <>
            <svg style={{ animation: 'spin 1s linear infinite', width: '18px', height: '18px' }} fill="none" viewBox="0 0 24 24">
              <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Comparaison en cours...</span>
          </>
        ) : (
          <>
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span>Comparer avec l'original</span>
          </>
        )}
      </button>

      {!canCompare && meshInfo && !meshInfo.isCompared && (
        <div style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)', textAlign: 'center' }}>
          Simplifiez ou retopologisez d'abord le mesh pour pouvoir le comparer.
        </div>
      )}

      {/* Load heatmap button */}
      {taskCompleted && !meshInfo?.isCompared && (
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

      {/* Back to mesh button when viewing heatmap */}
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
          Retour au mesh
        </button>
      )}

      {/* Stats display */}
      {stats && (
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
            { label: 'Hausdorff (max)', value: `${stats.hausdorff_pct}%` },
            { label: 'Distance moyenne', value: `${stats.mean_pct}%` },
            { label: 'RMS', value: stats.rms?.toFixed(6) },
            { label: 'P95', value: stats.p95?.toFixed(6) },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
              <span style={{ color: 'var(--v2-text-secondary)' }}>{label}</span>
              <span style={{ color: 'var(--v2-text-primary)', fontWeight: 500, fontFamily: 'monospace' }}>{value}</span>
            </div>
          ))}

          {/* Color legend */}
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

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default CompareControls
