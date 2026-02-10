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
        Le mesh tombe sous la gravite. Lancez des spheres pour tester les collisions.
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
