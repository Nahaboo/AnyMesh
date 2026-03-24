import { useState, useEffect, useCallback } from 'react'
import { getQualityStats } from '../utils/api'

const StatRow = ({ label, value, warn }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', padding: '2px 0' }}>
    <span style={{ color: 'var(--v2-text-secondary)' }}>{label}</span>
    <span style={{
      color: warn ? '#f59e0b' : 'var(--v2-accent-primary)',
      fontWeight: 500,
      fontFamily: 'monospace'
    }}>
      {value} {warn ? '\u26A0' : '\u2713'}
    </span>
  </div>
)

const ToggleRow = ({ label, isOn, onSetOn, onSetOff, disabled, color }) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '6px 0',
  }}>
    <span style={{
      fontSize: '0.8125rem',
      fontWeight: 500,
      color: disabled ? 'var(--v2-text-muted)' : 'var(--v2-text-primary)',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    }}>
      {color && <span style={{ width: 10, height: 10, borderRadius: 2, background: disabled ? 'var(--v2-text-muted)' : color, display: 'inline-block', opacity: disabled ? 0.3 : 1 }} />}
      {label}
    </span>
    <div style={{ display: 'flex', gap: '0px' }}>
      <button
        onClick={onSetOn}
        disabled={disabled}
        style={{
          padding: '2px 10px',
          fontSize: '0.6875rem',
          fontWeight: 600,
          border: '1px solid var(--v2-border-secondary)',
          borderRadius: '4px 0 0 4px',
          background: isOn ? (color || 'var(--v2-accent-primary)') : 'transparent',
          color: isOn ? '#fff' : (disabled ? 'var(--v2-text-muted)' : 'var(--v2-text-secondary)'),
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.4 : 1,
        }}
      >
        On
      </button>
      <button
        onClick={onSetOff}
        disabled={disabled}
        style={{
          padding: '2px 10px',
          fontSize: '0.6875rem',
          fontWeight: 600,
          border: '1px solid var(--v2-border-secondary)',
          borderRadius: '0 4px 4px 0',
          background: !isOn ? 'var(--v2-bg-tertiary)' : 'transparent',
          color: !isOn ? 'var(--v2-text-primary)' : (disabled ? 'var(--v2-text-muted)' : 'var(--v2-text-secondary)'),
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.4 : 1,
        }}
      >
        Off
      </button>
    </div>
  </div>
)

/**
 * QualityControls - MeshLab-style mesh quality diagnostics.
 * On/Off toggles for each diagnostic overlay (boundary edges, non-manifold, etc.)
 * Face Quality heatmap uses vertex-colored GLB.
 */
function QualityControls({ meshInfo, onOverlayChange }) {
  const [stats, setStats] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState(null)

  // Track which overlays are active (multiple can be on simultaneously)
  const [activeOverlays, setActiveOverlays] = useState({
    boundary: false,
    non_manifold: false,
  })

  const canAnalyze = !!meshInfo

  // Build overlays array from active toggles and push to parent
  const syncOverlays = useCallback((overlays, currentStats) => {
    if (!onOverlayChange || !currentStats) return
    const result = []
    if (overlays.boundary && currentStats.boundary_edge_positions?.length > 0) {
      result.push({ positions: currentStats.boundary_edge_positions, color: '#ff3333', type: 'boundary' })
    }
    if (overlays.non_manifold && currentStats.non_manifold_edge_positions?.length > 0) {
      result.push({ positions: currentStats.non_manifold_edge_positions, color: '#ff9900', type: 'non_manifold' })
    }
    onOverlayChange(result)
  }, [onOverlayChange])

  // Clear overlays on unmount
  useEffect(() => {
    return () => {
      if (onOverlayChange) onOverlayChange([])
    }
  }, [])

  // Clear stats when mesh changes
  useEffect(() => {
    setStats(null)
    setActiveOverlays({ boundary: false, non_manifold: false })
    if (onOverlayChange) onOverlayChange([])
  }, [meshInfo?.filename, meshInfo?.uploadId])

  const handleAnalyze = async () => {
    if (!meshInfo) return
    setIsAnalyzing(true)
    setError(null)

    try {
      const result = await getQualityStats(meshInfo.filename, {
        isGenerated: meshInfo.isGenerated || false,
        isSimplified: meshInfo.isSimplified || false,
        isRetopologized: meshInfo.isRetopologized || false,
      })

      if (result.success) {
        setStats(result)
      } else {
        setError(result.error || 'Analyse echouee')
      }
    } catch (err) {
      setError(err.message || 'Erreur reseau')
    }

    setIsAnalyzing(false)
  }

  const handleSetOverlay = (type, value) => {
    if (!stats) return
    const newOverlays = { ...activeOverlays, [type]: value }
    setActiveOverlays(newOverlays)
    syncOverlays(newOverlays, stats)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
      {/* Info */}
      <div style={{
        fontSize: '0.8125rem',
        color: 'var(--v2-text-secondary)',
        lineHeight: 1.5
      }}>
        Analyse la qualite topologique et geometrique du mesh.
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
            {(meshInfo.faces_count || meshInfo.triangles_count || 0).toLocaleString()} faces / {(meshInfo.vertices_count || 0).toLocaleString()} vertices
          </div>
        </div>
      )}

      {/* Analyze button */}
      <button
          onClick={handleAnalyze}
          disabled={!canAnalyze || isAnalyzing}
          className="v2-btn"
          style={{
            width: '100%',
            background: canAnalyze && !isAnalyzing ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
            color: canAnalyze && !isAnalyzing ? '#ffffff' : 'var(--v2-text-muted)',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            borderRadius: 'var(--v2-radius-lg)',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            cursor: canAnalyze && !isAnalyzing ? 'pointer' : 'not-allowed',
            border: 'none'
          }}
        >
          {isAnalyzing ? (
            <>
              <svg style={{ animation: 'spin 1s linear infinite', width: '18px', height: '18px' }} fill="none" viewBox="0 0 24 24">
                <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Analyse en cours...</span>
            </>
          ) : (
            <>
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Analyser la qualite</span>
            </>
          )}
      </button>

      {error && (
        <div style={{ fontSize: '0.75rem', color: '#ef4444', textAlign: 'center' }}>{error}</div>
      )}

      {/* MeshLab-style On/Off toggles */}
      {stats && (
        <div style={{
          padding: 'var(--v2-spacing-md)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-md)',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <ToggleRow
            label="Boundary Edges"
            isOn={activeOverlays.boundary}
            onSetOn={() => handleSetOverlay('boundary', true)}
            onSetOff={() => handleSetOverlay('boundary', false)}
            disabled={stats.boundary_edges === 0}
            color="#ff3333"
          />
          <ToggleRow
            label="Non-Manifold Edges"
            isOn={activeOverlays.non_manifold}
            onSetOn={() => handleSetOverlay('non_manifold', true)}
            onSetOff={() => handleSetOverlay('non_manifold', false)}
            disabled={stats.non_manifold_edges === 0}
            color="#ff9900"
          />
        </div>
      )}

      {/* Stats display */}
      {stats && (
        <div style={{
          padding: 'var(--v2-spacing-md)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--v2-spacing-xs)'
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--v2-text-secondary)', marginBottom: '4px' }}>
            Topology
          </div>
          <StatRow label="Boundary Edges" value={stats.boundary_edges.toLocaleString()} warn={stats.boundary_edges > 0} />
          <StatRow label="Boundary Faces" value={stats.boundary_faces.toLocaleString()} warn={stats.boundary_faces > 0} />
          <StatRow label="Non-Manifold Edges" value={stats.non_manifold_edges.toLocaleString()} warn={stats.non_manifold_edges > 0} />
          <StatRow label="Non-Manifold Vertices" value={stats.non_manifold_vertices.toLocaleString()} warn={stats.non_manifold_vertices > 0} />
          <StatRow label="Degenerate Faces" value={stats.degenerate_faces.toLocaleString()} warn={stats.degenerate_faces > 0} />

          <div style={{ height: '1px', background: 'var(--v2-border-secondary)', margin: '4px 0' }} />

          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--v2-text-secondary)', marginBottom: '4px' }}>
            Properties
          </div>
          <StatRow label="Watertight" value={stats.is_watertight ? 'Yes' : 'No'} warn={!stats.is_watertight} />
          <StatRow label="Consistent Normals" value={stats.is_winding_consistent ? 'Yes' : 'No'} warn={!stats.is_winding_consistent} />
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

export default QualityControls
