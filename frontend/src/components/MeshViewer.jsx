import { Suspense, useRef, useState, useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import MeshModel from './MeshModel'
import CameraController from './CameraController'

function MeshViewer({ meshInfo }) {
  const canvasContainerRef = useRef(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const toggleFullscreen = () => {
    if (!canvasContainerRef.current) return

    if (!document.fullscreenElement) {
      // Entrer en plein écran
      canvasContainerRef.current.requestFullscreen().then(() => {
        setIsFullscreen(true)
      }).catch((err) => {
        console.error('Erreur plein écran:', err)
      })
    } else {
      // Sortir du plein écran
      document.exitFullscreen().then(() => {
        setIsFullscreen(false)
      })
    }
  }

  // Ajouter/retirer l'écouteur au montage/démontage du composant
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [])

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800">
          Visualisation 3D
        </h2>
        {meshInfo && (
          <button
            onClick={toggleFullscreen}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title={isFullscreen ? "Quitter le plein écran" : "Plein écran"}
          >
            {isFullscreen ? (
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            )}
          </button>
        )}
      </div>

      {meshInfo ? (
        <div className="space-y-4">
          {/* Avertissement pour les gros fichiers */}
          {meshInfo.file_size > 5000000 && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
              <div className="flex items-start space-x-2">
                <svg className="w-5 h-5 text-orange-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-medium text-orange-800">
                    Fichier volumineux ({(meshInfo.file_size / 1024 / 1024).toFixed(1)} MB)
                  </p>
                  <p className="text-xs text-orange-700 mt-1">
                    Le chargement peut prendre quelques secondes. Pour de meilleures performances, pensez à simplifier le fichier.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Canvas 3D */}
          <div ref={canvasContainerRef} className="w-full h-96 bg-gray-100 rounded-lg overflow-hidden relative">
            <Canvas camera={{ position: [5, 5, 5], fov: 50 }}>
              {/* Ajustement automatique de la caméra */}
              {meshInfo.bounding_box && <CameraController boundingBox={meshInfo.bounding_box} />}

              {/* Lumieres */}
              <ambientLight intensity={0.5} />
              <directionalLight position={[10, 10, 5]} intensity={1} />
              <pointLight position={[-10, -10, -5]} intensity={0.5} />

              {/* Chargement du modèle 3D */}
              <Suspense fallback={
                <group>
                  <mesh>
                    <boxGeometry args={[2, 2, 2]} />
                    <meshStandardMaterial color="#3B82F6" wireframe />
                  </mesh>
                  <mesh rotation={[0, Math.PI / 4, 0]}>
                    <boxGeometry args={[1.5, 1.5, 1.5]} />
                    <meshStandardMaterial color="#60A5FA" wireframe />
                  </mesh>
                </group>
              }>
                <MeshModel
                  key={meshInfo.uploadId || meshInfo.filename}
                  filename={meshInfo.filename}
                />
              </Suspense>

              {/* Grille */}
              <Grid args={[10, 10]} />

              {/* Controles */}
              <OrbitControls
                enableDamping
                dampingFactor={0.05}
              />
            </Canvas>
          </div>

          {/* Informations du maillage */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="font-medium text-gray-800 mb-3">Informations du maillage</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-gray-500">Fichier:</p>
                <p className="font-semibold text-gray-900">{meshInfo.filename}</p>
              </div>
              <div>
                <p className="text-gray-500">Format:</p>
                <p className="font-semibold text-gray-900">{meshInfo.format}</p>
              </div>
              <div>
                <p className="text-gray-500">Vertices:</p>
                <p className="font-semibold text-gray-900">
                  {meshInfo.vertices_count?.toLocaleString() || 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-gray-500">Triangles:</p>
                <p className="font-semibold text-gray-900">
                  {meshInfo.triangles_count?.toLocaleString() || 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-gray-500">Taille:</p>
                <p className="font-semibold text-gray-900">
                  {(meshInfo.file_size / 1024).toFixed(2)} KB
                </p>
              </div>
              <div>
                <p className="text-gray-500">Manifold:</p>
                <p className="font-semibold text-gray-900">
                  {meshInfo.is_manifold === null ? 'N/A' : (meshInfo.is_manifold ? 'Oui' : 'Non')}
                </p>
              </div>
            </div>
          </div>

          {/* Controles de la vue */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
            <p className="text-xs text-gray-600">
              <strong>Contrôles 3D :</strong> Clic gauche pour tourner • Molette pour zoomer • Clic droit pour déplacer
            </p>
          </div>
        </div>
      ) : (
        <div className="w-full h-96 bg-gray-100 rounded-lg flex items-center justify-center">
          <div className="text-center text-gray-500">
            <svg className="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <p className="text-sm">Aucun maillage chargé</p>
            <p className="text-xs mt-1">Uploadez un fichier 3D pour commencer</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default MeshViewer
