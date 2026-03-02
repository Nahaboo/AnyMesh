import { useState } from 'react'

const StatRow = ({ label, value }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', padding: '2px 0' }}>
    <span style={{ color: 'var(--v2-text-secondary)' }}>{label}</span>
    <span style={{ color: 'var(--v2-accent-primary)', fontWeight: 500, fontFamily: 'monospace' }}>
      {value}
    </span>
  </div>
)

function UVUnwrapControls({ meshInfo, onUnwrapUV, onLoadUnwrapped, onLoadOriginal, onUVCheckerChange, currentTask, isProcessing }) {
  const busy = isProcessing
  const taskDone = currentTask?.taskType === 'unwrap_uv' && currentTask?.status === 'completed' && currentTask?.result?.success
  const taskFailed = currentTask?.taskType === 'unwrap_uv' && currentTask?.status === 'failed'
  const taskError = taskFailed
    ? (currentTask?.error || currentTask?.result?.error || 'Erreur inconnue')
    : currentTask?.taskType === 'unwrap_uv' && currentTask?.status === 'completed' && !currentTask?.result?.success
      ? (currentTask?.result?.error || 'Erreur inconnue')
      : null

  const handleUnwrap = () => {
    if (!meshInfo || !onUnwrapUV) return
    onUnwrapUV({
      filename: meshInfo.filename,
      isGenerated: meshInfo.isGenerated || false,
      isSimplified: meshInfo.isSimplified || false,
      isRetopologized: meshInfo.isRetopologized || false,
    })
  }

  const handleLoadUnwrapped = () => {
    if (!onLoadUnwrapped) return
    onLoadUnwrapped()
  }

  // UV Checker: 'off' | 'before' | 'after'
  const [checkerState, setCheckerState] = useState('off')

  const handleCheckerBefore = () => {
    setCheckerState('before')
    if (onUVCheckerChange) onUVCheckerChange(true)
    if (onLoadOriginal) onLoadOriginal()
  }

  const handleCheckerAfter = () => {
    setCheckerState('after')
    if (onUVCheckerChange) onUVCheckerChange(true)
    if (onLoadUnwrapped) onLoadUnwrapped()
  }

  const handleCheckerOff = () => {
    setCheckerState('off')
    if (onUVCheckerChange) onUVCheckerChange(false)
    if (onLoadOriginal) onLoadOriginal()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>

      {/* Description */}
      <p style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)', margin: 0 }}>
        Genere des UVs propres via LSCM (Least Squares Conformal Maps). Necessaire pour le baking et l'export production.
      </p>

      {/* Unwrap button */}
      <button
        onClick={handleUnwrap}
        disabled={busy || !meshInfo}
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
          cursor: (busy || !meshInfo) ? 'not-allowed' : 'pointer',
          opacity: (busy || !meshInfo) ? 0.5 : 1,
          border: 'none',
        }}
      >
        {busy && currentTask?.taskType === 'unwrap_uv' ? (
          <>
            <svg style={{ animation: 'spin 1s linear infinite', width: 18, height: 18 }} fill="none" viewBox="0 0 24 24">
              <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Unwrapping...</span>
          </>
        ) : (
          <>
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
            </svg>
            <span>Unwrap UV</span>
          </>
        )}
      </button>

      {/* Error */}
      {taskError && (
        <div style={{
          padding: 'var(--v2-spacing-sm)',
          background: 'rgba(239,68,68,0.1)',
          borderRadius: 'var(--v2-radius-sm)',
          border: '1px solid rgba(239,68,68,0.3)',
          fontSize: '0.75rem',
          color: '#ef4444',
        }}>
          {taskError}
        </div>
      )}

      {/* Results */}
      {taskDone && currentTask.result && (
        <div style={{
          padding: 'var(--v2-spacing-sm)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-sm)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}>
          <StatRow label="Vertices" value={currentTask.result.vertices_count?.toLocaleString()} />
          <StatRow label="Faces" value={currentTask.result.faces_count?.toLocaleString()} />
          <StatRow label="Couverture UV" value={`${currentTask.result.uv_coverage ?? '—'}%`} />
        </div>
      )}

      {/* UV Checker : Avant / Après / Off */}
      {taskDone && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)' }}>
            UV Checker — comparez les UVs avant et apres unwrap
          </span>
          <div style={{ display: 'flex', gap: 0 }}>
            {[
              { key: 'before', label: 'Avant' },
              { key: 'after',  label: 'Apres'  },
              { key: 'off',    label: 'Off'    },
            ].map(({ key, label }, i, arr) => (
              <button
                key={key}
                onClick={key === 'before' ? handleCheckerBefore : key === 'after' ? handleCheckerAfter : handleCheckerOff}
                style={{
                  flex: 1,
                  padding: '3px 0',
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  border: '1px solid var(--v2-border-secondary)',
                  borderLeft: i > 0 ? 'none' : '1px solid var(--v2-border-secondary)',
                  borderRadius: i === 0 ? '4px 0 0 4px' : i === arr.length - 1 ? '0 4px 4px 0' : '0',
                  background: checkerState === key ? 'var(--v2-accent-primary)' : 'transparent',
                  color: checkerState === key ? '#fff' : 'var(--v2-text-secondary)',
                  cursor: 'pointer',
                }}
              >{label}</button>
            ))}
          </div>
        </div>
      )}

      {/* Load unwrapped button */}
      {taskDone && (
        <button
          onClick={handleLoadUnwrapped}
          className="v2-btn v2-btn-secondary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm)',
            borderRadius: 'var(--v2-radius-lg)',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            cursor: 'pointer',
          }}
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          <span>Voir le mesh unwrappe</span>
        </button>
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

export default UVUnwrapControls
