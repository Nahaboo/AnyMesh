import { useLoader } from '@react-three/fiber'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { Center } from '@react-three/drei'

/**
 * Composant qui charge et affiche un fichier OBJ 3D
 */
function MeshModel({ filename }) {
  // Construire l'URL du fichier sur le backend
  const meshUrl = `http://localhost:8000/mesh/input/${filename}`

  console.log('Chargement du mesh depuis:', meshUrl)

  // Charger le modèle OBJ (useLoader doit être appelé inconditionnellement)
  const obj = useLoader(OBJLoader, meshUrl)

  console.log('Mesh chargé:', obj)

  return (
    <Center>
      <primitive
        object={obj}
        scale={[10, 10, 10]}
      />
    </Center>
  )
}

export default MeshModel
