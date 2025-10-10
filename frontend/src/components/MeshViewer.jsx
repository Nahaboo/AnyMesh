import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Center } from '@react-three/drei'

function MeshViewer({ meshInfo }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">
        Visualisation 3D
      </h2>

      {meshInfo ? (
        <div className="space-y-4">
          {/* Canvas 3D */}
          <div className="w-full h-96 bg-gray-100 rounded-lg overflow-hidden">
            <Canvas camera={{ position: [5, 5, 5], fov: 50 }}>
              {/* Lumieres */}
              <ambientLight intensity={0.5} />
              <directionalLight position={[10, 10, 5]} intensity={1} />
              <pointLight position={[-10, -10, -5]} intensity={0.5} />

              {/* Objet 3D placeholder */}
              <Center>
                <mesh>
                  <boxGeometry args={[2, 2, 2]} />
                  <meshStandardMaterial color="#4A90E2" />
                </mesh>
              </Center>

              {/* Grille */}
              <Grid args={[10, 10]} />

              {/* Controles */}
              <OrbitControls
                enableDamping
                dampingFactor={0.05}
                minDistance={2}
                maxDistance={20}
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
                  {meshInfo.is_manifold ? '✓ Oui' : '✗ Non'}
                </p>
              </div>
            </div>
          </div>

          {/* Note */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-xs text-blue-700">
              <strong>Note:</strong> La visualisation 3D complete avec chargement des fichiers OBJ/STL sera implementee dans une prochaine version. Pour l'instant, un cube placeholder est affiche.
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
