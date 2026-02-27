import { useState } from 'react'
import { generateMaterial, pollTaskStatus } from '../utils/api'

export const MATERIAL_PRESETS = [
  { id: 'rubber', label: 'Caoutchouc', mass: 1.0, restitution: 0.85, damping: 0.3, icon: 'circle', visual: { color: '#2a2a2a', metalness: 0.0, roughness: 0.85, opacity: 1.0 }, procedural: { type: 'leather', scale: 3.0, blendSharpness: 2.0 } },
  { id: 'wood', label: 'Bois', mass: 1.5, restitution: 0.3, damping: 0.6, icon: 'square', visual: { color: '#5C3A1E', metalness: 0.0, roughness: 0.9, opacity: 1.0 }, procedural: { type: 'wood', scale: 2.0, blendSharpness: 2.0 } },
  { id: 'metal', label: 'Metal', mass: 5.0, restitution: 0.15, damping: 0.2, icon: 'hexagon', visual: { color: '#C0C0C0', metalness: 0.95, roughness: 0.15, opacity: 1.0 }, procedural: { type: 'metal', scale: 3.0, blendSharpness: 3.0 } },
  { id: 'glass', label: 'Verre', mass: 2.5, restitution: 0.5, damping: 0.1, icon: 'diamond', visual: { color: '#E8F4FD', metalness: 0.1, roughness: 0.05, opacity: 0.4, transparent: true } },
  { id: 'foam', label: 'Mousse', mass: 0.2, restitution: 0.05, damping: 0.9, icon: 'cloud', visual: { color: '#E8D44D', metalness: 0.0, roughness: 1.0, opacity: 1.0 }, procedural: { type: 'foam', scale: 4.0, blendSharpness: 2.0 } },
  { id: 'stone', label: 'Pierre', mass: 4.0, restitution: 0.1, damping: 0.7, icon: 'triangle', visual: { color: '#4A4A4A', metalness: 0.25, roughness: 0.5, opacity: 1.0 }, procedural: { type: 'stone', scale: 3.0, blendSharpness: 2.0 } }
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
const AI_MATERIAL_EXAMPLES = ['Marble', 'Carbon Fiber', 'Rubber', 'Oak Wood', 'Steel']

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
  onResetMaterial,
  onAIMaterialGenerated,
  onReset,
  onExit
}) {
  const [aiPrompt, setAiPrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [aiError, setAiError] = useState('')

  const handleGenerateMaterial = async () => {
    if (!aiPrompt.trim() || isGenerating) return
    setIsGenerating(true)
    setAiError('')
    try {
      const { task_id } = await generateMaterial({ prompt: aiPrompt.trim() })
      const result = await pollTaskStatus(task_id, null, 1500, 120)
      if (result.status === 'completed' && result.result?.success) {
        onAIMaterialGenerated?.({
          textureId: result.result.texture_id,
          physics: result.result.physics
        })
      } else {
        setAiError(result.result?.error || 'Echec de la generation')
      }
    } catch (e) {
      setAiError(e.message || 'Erreur reseau')
    } finally {
      setIsGenerating(false)
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
        <button
          onClick={onResetMaterial}
          style={{
            width: '100%',
            marginTop: 'var(--v2-spacing-xs)',
            padding: '6px var(--v2-spacing-sm)',
            borderRadius: 'var(--v2-radius-md)',
            border: !activePreset
              ? '2px solid var(--v2-accent-primary)'
              : '1px solid var(--v2-border-secondary)',
            background: !activePreset
              ? 'var(--v2-accent-primary-alpha, rgba(99, 102, 241, 0.1))'
              : 'var(--v2-bg-primary)',
            color: !activePreset
              ? 'var(--v2-accent-primary)'
              : 'var(--v2-text-secondary)',
            cursor: 'pointer',
            fontSize: '0.7rem',
            fontWeight: !activePreset ? 600 : 400,
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a5 5 0 010 10H9M3 10l4-4M3 10l4 4" />
          </svg>
          Texture originale
        </button>
      </div>

      {/* AI Material */}
      <div style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
        <label style={{
          fontSize: '0.875rem',
          fontWeight: 500,
          color: 'var(--v2-text-secondary)',
          marginBottom: 'var(--v2-spacing-sm)',
          display: 'block'
        }}>
          Materiau IA
        </label>
        <div style={{ display: 'flex', gap: 'var(--v2-spacing-xs)', marginBottom: 'var(--v2-spacing-xs)' }}>
          <input
            type="text"
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerateMaterial()}
            placeholder="Ex: marble, carbon fiber..."
            disabled={isGenerating}
            style={{
              flex: 1,
              padding: '6px 10px',
              borderRadius: 'var(--v2-radius-md)',
              border: '1px solid var(--v2-border-secondary)',
              background: 'var(--v2-bg-primary)',
              color: 'var(--v2-text-primary)',
              fontSize: '0.8rem'
            }}
          />
          <button
            className="v2-btn v2-btn-primary"
            onClick={handleGenerateMaterial}
            disabled={!aiPrompt.trim() || isGenerating}
            style={{ padding: '6px 12px', fontSize: '0.75rem', whiteSpace: 'nowrap' }}
          >
            {isGenerating ? '...' : 'Generer'}
          </button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {AI_MATERIAL_EXAMPLES.map(ex => (
            <button
              key={ex}
              onClick={() => setAiPrompt(ex)}
              disabled={isGenerating}
              style={{
                padding: '2px 8px',
                borderRadius: '12px',
                border: '1px solid var(--v2-border-secondary)',
                background: 'var(--v2-bg-primary)',
                color: 'var(--v2-text-muted)',
                fontSize: '0.65rem',
                cursor: 'pointer'
              }}
            >
              {ex}
            </button>
          ))}
        </div>
        {aiError && (
          <div style={{ color: 'var(--v2-error, #ef4444)', fontSize: '0.75rem', marginTop: '4px' }}>
            {aiError}
          </div>
        )}
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
