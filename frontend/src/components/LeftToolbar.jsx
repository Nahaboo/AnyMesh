/**
 * Left Toolbar - Vertical tools menu
 * Includes: Simplification, Segmentation, Retopology
 */
function LeftToolbar({ activeTool, onToolChange, meshInfo }) {
  // Vérifier si on visualise un mesh retopologisé
  const isRetopologizedMesh = meshInfo?.isRetopologized === true

  const tools = [
    {
      id: 'simplification',
      label: 'Simplification',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      enabled: !isRetopologizedMesh,
      disabledReason: isRetopologizedMesh ? 'Mesh retopologisé (quads). La simplification produirait des résultats dégradés. Workflow recommandé: Simplification → Retopologie.' : null
    },
    /* DISABLED - Refine (not implemented yet)
    {
      id: 'refine',
      label: 'Refine',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
        </svg>
      ),
      enabled: false
    },
    */
    {
      id: 'segmentation',
      label: 'Segmentation',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
        </svg>
      ),
      enabled: true
    },
    {
      id: 'retopoly',
      label: 'Retopoly',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5" />
        </svg>
      ),
      enabled: true
    }
    /* DISABLED - Texturing & Rigging (not implemented yet)
    {
      id: 'texturing',
      label: 'Texturing',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
      ),
      enabled: false
    },
    {
      id: 'rigging',
      label: 'Rigging',
      icon: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      ),
      enabled: false
    }
    */
  ]

  return (
    <div style={{
      width: 'var(--v2-toolbar-left-width)',
      height: '100%',
      background: 'var(--v2-bg-secondary)',
      borderRight: '1px solid var(--v2-border-secondary)',
      display: 'flex',
      flexDirection: 'column',
      paddingTop: 'var(--v2-spacing-md)',
      gap: 'var(--v2-spacing-xs)'
    }}>
      {tools.map(tool => (
        <button
          key={tool.id}
          onClick={() => tool.enabled && onToolChange(tool.id)}
          disabled={!tool.enabled}
          className={`v2-tool-button ${activeTool === tool.id ? 'active' : ''}`}
          title={tool.enabled ? tool.label : (tool.disabledReason || `${tool.label} (Coming soon)`)}
        >
          {tool.icon}
          <span>{tool.label}</span>
          {!tool.enabled && !tool.disabledReason && (
            <span style={{
              fontSize: '0.625rem',
              color: 'var(--v2-text-muted)',
              fontStyle: 'italic'
            }}>
              Soon
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

export default LeftToolbar
