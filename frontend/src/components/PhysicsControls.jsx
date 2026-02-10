const MATERIAL_PRESETS = [
  { id: 'rubber', label: 'Caoutchouc', mass: 1.0, restitution: 0.85, damping: 0.3, icon: 'circle' },
  { id: 'wood', label: 'Bois', mass: 1.5, restitution: 0.3, damping: 0.6, icon: 'square' },
  { id: 'metal', label: 'Metal', mass: 5.0, restitution: 0.15, damping: 0.2, icon: 'hexagon' },
  { id: 'glass', label: 'Verre', mass: 2.5, restitution: 0.5, damping: 0.1, icon: 'diamond' },
  { id: 'foam', label: 'Mousse', mass: 0.2, restitution: 0.05, damping: 0.9, icon: 'cloud' },
  { id: 'stone', label: 'Pierre', mass: 4.0, restitution: 0.1, damping: 0.7, icon: 'triangle' }
]

function PresetIcon({ type, size = 14 }) {
  const s = size
  if (type === 'circle') return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <circle cx="12" cy="12" r="10" />
    </svg>
  )
  if (type === 'square') return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
    </svg>
  )
  if (type === 'hexagon') return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" />
    </svg>
  )
  if (type === 'diamond') return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <polygon points="12,2 22,12 12,22 2,12" />
    </svg>
  )
  if (type === 'cloud') return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
    </svg>
  )
  if (type === 'triangle') return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <polygon points="12,3 22,21 2,21" />
    </svg>
  )
  return null
}

/**
 * PhysicsControls - Right panel for physics simulation parameters
 */
function PhysicsControls({
  gravity,
  onGravityChange,
  mass,
  onMassChange,
  restitution,
  onRestitutionChange,
  damping,
  onDampingChange,
  activePreset,
  onPresetChange,
  onThrowSphere,
  onReset,
  onExit,
  projectileCount
}) {
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
        Simulation Physique
      </h2>

      {/* Info box */}
      <div style={{
        background: 'var(--v2-info-bg)',
        border: '1px solid var(--v2-info-border)',
        borderRadius: 'var(--v2-radius-lg)',
        padding: 'var(--v2-spacing-md)',
        marginBottom: 'var(--v2-spacing-lg)',
        fontSize: '0.875rem',
        color: 'var(--v2-info-text)'
      }}>
        Choisissez un materiau ou ajustez les parametres manuellement.
      </div>

      {/* Material presets grid */}
      <div style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
        <label style={{
          fontSize: '0.875rem',
          fontWeight: 500,
          color: 'var(--v2-text-secondary)',
          marginBottom: 'var(--v2-spacing-sm)',
          display: 'block'
        }}>
          Materiau
        </label>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 'var(--v2-spacing-xs)'
        }}>
          {MATERIAL_PRESETS.map(preset => (
            <button
              key={preset.id}
              onClick={() => onPresetChange(preset)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '4px',
                padding: 'var(--v2-spacing-sm)',
                borderRadius: 'var(--v2-radius-md)',
                border: activePreset === preset.id
                  ? '2px solid var(--v2-accent-primary)'
                  : '1px solid var(--v2-border-secondary)',
                background: activePreset === preset.id
                  ? 'var(--v2-accent-primary-alpha, rgba(99, 102, 241, 0.1))'
                  : 'var(--v2-bg-primary)',
                color: activePreset === preset.id
                  ? 'var(--v2-accent-primary)'
                  : 'var(--v2-text-secondary)',
                cursor: 'pointer',
                fontSize: '0.7rem',
                fontWeight: activePreset === preset.id ? 600 : 400,
                transition: 'all 0.15s ease'
              }}
            >
              <PresetIcon type={preset.icon} />
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Gravity slider */}
      <div style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          <label style={{
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)'
          }}>
            Gravite
          </label>
          <span style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'var(--v2-text-primary)'
          }}>
            {gravity.toFixed(1)} m/s²
          </span>
        </div>
        <input
          type="range"
          min="-20"
          max="0"
          step="0.1"
          value={gravity}
          onChange={(e) => onGravityChange(parseFloat(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }}
        />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: 'var(--v2-text-muted)',
          marginTop: '2px'
        }}>
          <span>-20 (Jupiter)</span>
          <span>0 (Apesanteur)</span>
        </div>
      </div>

      {/* Mass slider */}
      <div style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          <label style={{
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)'
          }}>
            Masse
          </label>
          <span style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'var(--v2-text-primary)'
          }}>
            {Math.round(mass * 100)}%
          </span>
        </div>
        <input
          type="range"
          min="0.1"
          max="10"
          step="0.1"
          value={mass}
          onChange={(e) => onMassChange(parseFloat(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }}
        />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: 'var(--v2-text-muted)',
          marginTop: '2px'
        }}>
          <span>10% (leger)</span>
          <span>1000% (lourd)</span>
        </div>
      </div>

      {/* Restitution slider */}
      <div style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          <label style={{
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)'
          }}>
            Rebond
          </label>
          <span style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'var(--v2-text-primary)'
          }}>
            {Math.round(restitution * 100)}%
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={restitution}
          onChange={(e) => onRestitutionChange(parseFloat(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }}
        />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: 'var(--v2-text-muted)',
          marginTop: '2px'
        }}>
          <span>0% (mou)</span>
          <span>100% (balle)</span>
        </div>
      </div>

      {/* Damping slider */}
      <div style={{ marginBottom: 'var(--v2-spacing-xl)' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          <label style={{
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)'
          }}>
            Amortissement
          </label>
          <span style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'var(--v2-text-primary)'
          }}>
            {Math.round(damping * 100)}%
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={damping}
          onChange={(e) => onDampingChange(parseFloat(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }}
        />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: 'var(--v2-text-muted)',
          marginTop: '2px'
        }}>
          <span>0% (glissant)</span>
          <span>100% (visqueux)</span>
        </div>
      </div>

      {/* Action buttons */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--v2-spacing-sm)'
      }}>
        <button
          className="v2-btn v2-btn-primary"
          onClick={onThrowSphere}
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-sm)'
          }}
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" strokeWidth={2} />
          </svg>
          Lancer une sphere ({projectileCount}/10)
        </button>

        <button
          className="v2-btn v2-btn-secondary"
          onClick={onReset}
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)'
          }}
        >
          Reinitialiser
        </button>

        <button
          className="v2-btn v2-btn-ghost"
          onClick={onExit}
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            marginTop: 'var(--v2-spacing-sm)'
          }}
        >
          Quitter le mode physique
        </button>
      </div>
    </div>
  )
}

export default PhysicsControls
