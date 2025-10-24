/**
 * Top Toolbar - Render mode selection and navigation
 * Includes: Solid, Wireframe, Normal Map, Flat modes
 * Plus Home button and app title
 */
function TopToolbar({ renderMode, onRenderModeChange, onHomeClick }) {
  const modes = [
    { id: 'solid', label: 'Solid' },
    { id: 'wireframe', label: 'Wireframe' },
    { id: 'normal', label: 'Normal Map' },
    { id: 'flat', label: 'Flat' }
  ]

  return (
    <div style={{
      height: 'var(--v2-toolbar-height)',
      background: 'var(--v2-bg-secondary)',
      borderBottom: '1px solid var(--v2-border-secondary)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 var(--v2-spacing-lg)',
      position: 'relative',
      zIndex: 10
    }}>
      {/* Left: App Title */}
      <div style={{
        fontSize: '1.125rem',
        fontWeight: 600,
        color: 'var(--v2-text-primary)'
      }}>
        Any 3d
      </div>

      {/* Center: Render Mode Buttons */}
      <div style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        gap: 'var(--v2-spacing-sm)',
        background: 'var(--v2-bg-tertiary)',
        padding: 'var(--v2-spacing-xs)',
        borderRadius: 'var(--v2-radius-md)'
      }}>
        {modes.map(mode => (
          <button
            key={mode.id}
            onClick={() => onRenderModeChange(mode.id)}
            className={`v2-toolbar-button ${renderMode === mode.id ? 'active' : ''}`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Right: Home Button */}
      <button
        onClick={onHomeClick}
        className="v2-btn v2-btn-secondary"
        style={{
          padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
          borderRadius: 'var(--v2-radius-full)'
        }}
      >
        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
        Home page
      </button>
    </div>
  )
}

export default TopToolbar
