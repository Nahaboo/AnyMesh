/**
 * GLB-First: SaveButton Component
 *
 * Allows users to save the current mesh with a custom name.
 * Part of the "save on demand" workflow.
 */
import { useState } from 'react'
import { saveMesh } from '../utils/api'

function SaveButton({ meshInfo, onSaved, disabled }) {
  const [showDialog, setShowDialog] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Generate default save name from mesh filename
  const getDefaultName = () => {
    if (!meshInfo?.filename) return ''
    const base = meshInfo.filename.replace(/\.[^/.]+$/, '') // Remove extension
    const timestamp = new Date().toISOString().slice(0, 10) // YYYY-MM-DD
    return `${base}_${timestamp}`
  }

  const handleOpenDialog = () => {
    setSaveName(getDefaultName())
    setError(null)
    setShowDialog(true)
  }

  const handleSave = async () => {
    if (!saveName.trim()) {
      setError('Nom requis')
      return
    }

    setSaving(true)
    setError(null)

    try {
      const result = await saveMesh(meshInfo.filename, saveName.trim())
      console.log('[SAVE] Mesh saved:', result)
      setShowDialog(false)
      setSaveName('')
      onSaved?.(result)
    } catch (err) {
      console.error('[SAVE] Error:', err)
      setError(err.response?.data?.detail || 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !saving) {
      handleSave()
    } else if (e.key === 'Escape') {
      setShowDialog(false)
    }
  }

  if (!meshInfo?.filename) {
    return null
  }

  return (
    <>
      <button
        onClick={handleOpenDialog}
        disabled={disabled}
        className="v2-save-button"
        title="Sauvegarder ce mesh"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          background: 'var(--v2-accent-primary)',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          fontSize: '13px',
          fontWeight: 500
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" />
          <polyline points="17,21 17,13 7,13 7,21" />
          <polyline points="7,3 7,8 15,8" />
        </svg>
        Sauvegarder
      </button>

      {showDialog && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowDialog(false)}
        >
          <div
            style={{
              background: 'var(--v2-bg-primary)',
              borderRadius: '12px',
              padding: '24px',
              minWidth: '320px',
              maxWidth: '400px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
            }}
            onClick={e => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 16px', color: 'var(--v2-text-primary)' }}>
              Sauvegarder le mesh
            </h3>

            <div style={{ marginBottom: '12px' }}>
              <label style={{
                display: 'block',
                marginBottom: '6px',
                fontSize: '13px',
                color: 'var(--v2-text-secondary)'
              }}>
                Nom de la sauvegarde
              </label>
              <input
                type="text"
                value={saveName}
                onChange={e => setSaveName(e.target.value)}
                onKeyDown={handleKeyDown}
                autoFocus
                placeholder="mon_mesh_v1"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid var(--v2-border-primary)',
                  borderRadius: '6px',
                  background: 'var(--v2-bg-secondary)',
                  color: 'var(--v2-text-primary)',
                  fontSize: '14px',
                  boxSizing: 'border-box'
                }}
              />
              <div style={{
                fontSize: '11px',
                color: 'var(--v2-text-muted)',
                marginTop: '4px'
              }}>
                Fichier source: {meshInfo.filename}
              </div>
            </div>

            {error && (
              <div style={{
                padding: '8px 12px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '6px',
                color: '#ef4444',
                fontSize: '13px',
                marginBottom: '12px'
              }}>
                {error}
              </div>
            )}

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowDialog(false)}
                style={{
                  padding: '8px 16px',
                  background: 'transparent',
                  border: '1px solid var(--v2-border-primary)',
                  borderRadius: '6px',
                  color: 'var(--v2-text-secondary)',
                  cursor: 'pointer'
                }}
              >
                Annuler
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !saveName.trim()}
                style={{
                  padding: '8px 16px',
                  background: 'var(--v2-accent-primary)',
                  border: 'none',
                  borderRadius: '6px',
                  color: 'white',
                  cursor: saving || !saveName.trim() ? 'not-allowed' : 'pointer',
                  opacity: saving || !saveName.trim() ? 0.5 : 1
                }}
              >
                {saving ? 'Sauvegarde...' : 'Confirmer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default SaveButton
