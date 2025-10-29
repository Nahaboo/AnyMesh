import ThemeToggle from './ThemeToggle'

/**
 * Top Toolbar - Render mode selection and navigation
 * Includes: Solid, Wireframe, Normal Map, Flat modes + Custom Shaders
 * Plus Home button, theme toggle, app title, and debug toggle
 */
function TopToolbar({ renderMode, onRenderModeChange, onHomeClick, debugMode, onDebugModeChange, isShaderMode }) {
  const modes = [
    { id: 'solid', label: 'Solid' },
    { id: 'wireframe', label: 'Wireframe' },
    { id: 'normal', label: 'Normal Map' },
    { id: 'flat', label: 'Flat' },
    { id: 'shader:toon', label: 'Toon', isShader: true },
    { id: 'shader:organic-solid', label: 'Organic', isShader: true },
    { id: 'shader:point-cloud', label: 'Point Cloud', isShader: true }
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

      {/* Right: Theme Toggle + Debug Button + Home Button */}
      <div style={{ display: 'flex', gap: 'var(--v2-spacing-sm)', alignItems: 'center' }}>
        {/* Theme toggle */}
        <ThemeToggle />

        {/* Debug button - only visible when a shader is active */}
        {isShaderMode && (
          <button
            onClick={() => onDebugModeChange(!debugMode)}
            className={`v2-btn ${debugMode ? 'v2-btn-primary' : 'v2-btn-secondary'}`}
            style={{
              padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
              borderRadius: 'var(--v2-radius-full)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--v2-spacing-xs)'
            }}
            title="Toggle shader debug panel (Ctrl+D)"
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {debugMode ? 'Hide Debug' : 'Debug'}
          </button>
        )}

        {/* Home button */}
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
    </div>
  )
}

export default TopToolbar
