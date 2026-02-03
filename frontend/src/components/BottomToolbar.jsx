import { useState } from 'react'
import SaveButton from './SaveButton'

/**
 * Bottom Toolbar - Export controls and mesh statistics
 * Left side: Export button + Format dropdown + Save button
 * Right side: Mesh info (Faces, Vertices) + 3D axes widget
 */
function BottomToolbar({ meshInfo, onExport, onMeshSaved, axesWidget }) {
  const [selectedFormat, setSelectedFormat] = useState('obj')
  const [showFormatMenu, setShowFormatMenu] = useState(false)

  const formats = [
    { id: 'obj', label: 'OBJ', extension: '.obj' },
    { id: 'stl', label: 'STL', extension: '.stl' },
    { id: 'ply', label: 'PLY', extension: '.ply' },
    { id: 'glb', label: 'GLB', extension: '.glb' }
  ]

  const handleExport = () => {
    const format = formats.find(f => f.id === selectedFormat)
    onExport(format)
    console.log(`[BottomToolbar] Exporting as ${format.label}`)
  }

  return (
    <div style={{
      position: 'absolute',
      bottom: 'var(--v2-spacing-lg)',
      left: 'var(--v2-toolbar-left-width)',
      right: 0,
      height: '60px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 var(--v2-spacing-lg)',
      pointerEvents: 'none'
    }}>
      {/* Left: Export Controls */}
      <div style={{
        display: 'flex',
        gap: 'var(--v2-spacing-sm)',
        pointerEvents: 'auto'
      }}>
        <button
          onClick={handleExport}
          className="v2-btn v2-btn-secondary"
          disabled={!meshInfo}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--v2-spacing-sm)'
          }}
        >
          <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export
        </button>

        {/* GLB-First: Save Button */}
        <SaveButton
          meshInfo={meshInfo}
          onSaved={onMeshSaved}
          disabled={!meshInfo}
        />

        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowFormatMenu(!showFormatMenu)}
            className="v2-btn v2-btn-secondary"
            disabled={!meshInfo}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--v2-spacing-sm)',
              minWidth: '100px',
              justifyContent: 'space-between'
            }}
          >
            <span>{selectedFormat.toUpperCase()}</span>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Format Dropdown Menu */}
          {showFormatMenu && (
            <>
              <div
                style={{
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  zIndex: 10
                }}
                onClick={() => setShowFormatMenu(false)}
              />
              <div style={{
                position: 'absolute',
                bottom: '100%',
                left: 0,
                marginBottom: 'var(--v2-spacing-xs)',
                background: 'var(--v2-bg-secondary)',
                border: '1px solid var(--v2-border-secondary)',
                borderRadius: 'var(--v2-radius-md)',
                boxShadow: 'var(--v2-shadow-lg)',
                minWidth: '120px',
                zIndex: 20,
                overflow: 'hidden'
              }}>
                {formats.map(format => (
                  <button
                    key={format.id}
                    onClick={() => {
                      setSelectedFormat(format.id)
                      setShowFormatMenu(false)
                    }}
                    style={{
                      width: '100%',
                      padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
                      background: selectedFormat === format.id ? 'var(--v2-bg-hover)' : 'transparent',
                      border: 'none',
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontSize: '0.875rem',
                      color: 'var(--v2-text-primary)',
                      transition: 'background var(--v2-transition-fast)'
                    }}
                    onMouseEnter={(e) => e.target.style.background = 'var(--v2-bg-hover)'}
                    onMouseLeave={(e) => {
                      if (selectedFormat !== format.id) {
                        e.target.style.background = 'transparent'
                      }
                    }}
                  >
                    {format.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Right: Mesh Info + 3D Axes */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--v2-spacing-lg)',
        pointerEvents: 'auto'
      }}>
        {/* Mesh Statistics */}
        {meshInfo && (
          <div className="v2-viewer-stats" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--v2-spacing-xs)',
            minWidth: '140px'
          }}>
            <div style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-xs)'
            }}>
              Informations
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.75rem'
            }}>
              <span style={{ color: 'var(--v2-text-secondary)' }}>Faces</span>
              <span style={{ color: 'var(--v2-text-primary)', fontWeight: 500 }}>
                {(meshInfo.triangles_count || meshInfo.faces_count || 0).toLocaleString()}
              </span>
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.75rem'
            }}>
              <span style={{ color: 'var(--v2-text-secondary)' }}>Vertices</span>
              <span style={{ color: 'var(--v2-text-primary)', fontWeight: 500 }}>
                {meshInfo.vertices_count?.toLocaleString() || 0}
              </span>
            </div>
          </div>
        )}

        {/* 3D Axes Widget - Rendered by parent */}
        {axesWidget}
      </div>
    </div>
  )
}

export default BottomToolbar
