import { useTheme } from '../hooks/useTheme'

/**
 * ThemeToggle - Bouton pour basculer entre thème clair et sombre
 * Affiche une icône soleil (light) ou lune (dark)
 */
function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      onClick={toggleTheme}
      className="v2-btn v2-btn-ghost"
      title={isDark ? 'Passer en mode clair' : 'Passer en mode sombre'}
      style={{
        padding: 'var(--v2-spacing-sm)',
        width: '40px',
        height: '40px'
      }}
    >
      {isDark ? (
        // Icône Soleil (pour passer en light mode)
        <svg
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          style={{ transition: 'transform var(--v2-transition-base)' }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      ) : (
        // Icône Lune (pour passer en dark mode)
        <svg
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          style={{ transition: 'transform var(--v2-transition-base)' }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      )}
    </button>
  )
}

export default ThemeToggle
