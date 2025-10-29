import { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext(undefined)

/**
 * ThemeProvider - Gère l'état global du thème (light/dark)
 * - Persiste le thème dans localStorage
 * - Applique l'attribut data-theme sur <html>
 */
export function ThemeProvider({ children }) {
  // Initialiser le thème depuis localStorage ou système
  const [theme, setTheme] = useState(() => {
    // 1. Vérifier localStorage
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme === 'light' || savedTheme === 'dark') {
      return savedTheme
    }

    // 2. Détecter préférence système
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }

    // 3. Défaut : light
    return 'light'
  })

  // Appliquer le thème au DOM et persister
  useEffect(() => {
    // Appliquer data-theme sur <html>
    document.documentElement.setAttribute('data-theme', theme)

    // Persister dans localStorage
    localStorage.setItem('theme', theme)

    console.log(`[ThemeProvider] Theme changed to: ${theme}`)
  }, [theme])

  // Écouter les changements de préférence système
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const handleChange = (e) => {
      // Uniquement si l'utilisateur n'a pas explicitement choisi un thème
      const savedTheme = localStorage.getItem('theme')
      if (!savedTheme) {
        setTheme(e.matches ? 'dark' : 'light')
      }
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  const value = {
    theme,
    setTheme,
    toggleTheme,
    isDark: theme === 'dark'
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

/**
 * Hook pour accéder au thème
 * @returns {{ theme: 'light' | 'dark', setTheme: Function, toggleTheme: Function, isDark: boolean }}
 */
export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
