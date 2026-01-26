import { Component } from 'react'

/**
 * Q5: Error Boundary pour capturer les erreurs de chargement 3D
 * Affiche un cube rouge wireframe au lieu de crasher l'application
 */
class ModelErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ModelErrorBoundary] 3D loading failed:', error)
    console.error('[ModelErrorBoundary] Component stack:', errorInfo.componentStack)
  }

  render() {
    if (this.state.hasError) {
      // Afficher un cube rouge wireframe comme fallback
      return (
        <mesh>
          <boxGeometry args={[2, 2, 2]} />
          <meshStandardMaterial color="#ef4444" wireframe />
        </mesh>
      )
    }
    return this.props.children
  }
}

export default ModelErrorBoundary
