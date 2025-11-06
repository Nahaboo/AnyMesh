import { Suspense, useRef, useState, useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import MeshModel from './MeshModel'
import CameraController from './CameraController'
import { analyzeMesh } from '../utils/api'

function MeshViewer({ meshInfo }) {
  const canvasContainerRef = useRef(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [meshStats, setMeshStats] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState(null)

  // Lancer l'analyse en arrière-plan quand le mesh change
  useEffect(() => {
    if (!meshInfo) return

    // Utiliser originalFilename si disponible, sinon filename
    const filenameToAnalyze = meshInfo.originalFilename || meshInfo.filename

    if (!filenameToAnalyze) return

    const runAnalysis = async () => {
      setIsAnalyzing(true)
      setAnalysisError(null)
      setMeshStats(null)

      try {
        console.log(`🔵 [MeshViewer] Lancement analyse en arrière-plan: ${filenameToAnalyze}`)
        const result = await analyzeMesh(filenameToAnalyze)

        if (result.success) {
          console.log(`🟢 [MeshViewer] Analyse terminée: ${result.analysis_time_ms}ms`)
          setMeshStats(result.mesh_stats)
        }
      } catch (error) {
        console.error('❌ [MeshViewer] Erreur analyse:', error)
        setAnalysisError(error.message || 'Erreur lors de l\'analyse')
      } finally {
        setIsAnalyzing(false)
      }
    }

    // Délai plus long pour vraiment laisser le 3D se charger d'abord
    const timeout = setTimeout(runAnalysis, 500)
    return () => clearTimeout(timeout)
  }, [meshInfo])

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
                  isGenerated={meshInfo.isGenerated || false}
                  isSegmented={meshInfo.isSegmented || false}
                  isSimplified={meshInfo.isSimplified || false}
                  isRetopologized={meshInfo.isRetopologized || false}
                />
              </Suspense>

              {/* Axes x, y, z (rouge, vert, bleu) */}
              <axesHelper args={[5]} />

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

            {/* Informations de base (toujours disponibles) */}
            <div className="grid grid-cols-2 gap-3 text-sm mb-3">
              <div>
                <p className="text-gray-500">Fichier:</p>
                <p className="font-semibold text-gray-900">{meshInfo.filename}</p>
              </div>
              <div>
                <p className="text-gray-500">Format:</p>
                <p className="font-semibold text-gray-900">{meshInfo.format}</p>
              </div>
              <div>
                <p className="text-gray-500">Taille:</p>
                <p className="font-semibold text-gray-900">
                  {(meshInfo.file_size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>

            {/* Statistiques détaillées (chargées en arrière-plan) */}
            {isAnalyzing && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Analyse du maillage en cours...</span>
                </div>
              </div>
            )}

            {analysisError && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-sm text-red-600">⚠️ {analysisError}</p>
              </div>
            )}

            {meshStats && !isAnalyzing && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs text-gray-500 mb-2">Statistiques détaillées:</p>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-gray-500">Vertices:</p>
                    <p className="font-semibold text-gray-900">
                      {meshStats.vertices_count?.toLocaleString() || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">Triangles:</p>
                    <p className="font-semibold text-gray-900">
                      {meshStats.triangles_count?.toLocaleString() || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">Watertight:</p>
                    <p className="font-semibold text-gray-900">
                      {meshStats.is_watertight ? 'Oui' : 'Non'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">Manifold:</p>
                    <p className="font-semibold text-gray-900">
                      {meshStats.is_manifold === null ? 'N/A' : (meshStats.is_manifold ? 'Oui' : 'Non')}
                    </p>
                  </div>
                  {meshStats.volume && (
                    <div className="col-span-2">
                      <p className="text-gray-500">Volume:</p>
                      <p className="font-semibold text-gray-900">
                        {meshStats.volume.toFixed(3)}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
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
