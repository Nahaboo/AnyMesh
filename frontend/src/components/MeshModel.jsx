import { useEffect } from 'react'
import { useLoader } from '@react-three/fiber'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader'
import { Center } from '@react-three/drei'
import * as THREE from 'three'
import perf from '../utils/performance'

/**
 * Composant qui charge et affiche un fichier 3D (OBJ, GLTF, GLB, STL, PLY)
 */
function MeshModel({ filename }) {
  // Construire l'URL du fichier sur le backend
  const meshUrl = `http://localhost:8000/mesh/input/${filename}`

  // Déterminer le format du fichier
  const extension = filename.split('.').pop().toLowerCase()

  console.log('Chargement du mesh depuis:', meshUrl, 'Format:', extension)

  // Démarrer le timer de chargement (une seule fois au montage)
  useEffect(() => {
    // Réinitialiser les mesures précédentes
    perf.reset()

    const totalLabel = `TOTAL_LOAD_${filename}`
    const fetchParseLabel = `FETCH_AND_PARSE_${extension.toUpperCase()}_${filename}`

    perf.start(totalLabel)
    perf.start(fetchParseLabel)

    // Note: useLoader combine fetch + parse de manière synchrone
    // On ne peut pas séparer facilement ces deux étapes
  }, [filename, extension])

  // Charger le modèle selon le format
  // Note: useLoader gère le téléchargement réseau + parsing de manière bloquante
  let model

  if (extension === 'obj') {
    model = useLoader(OBJLoader, meshUrl)
  } else if (extension === 'gltf' || extension === 'glb') {
    const gltf = useLoader(GLTFLoader, meshUrl)
    model = gltf.scene
  } else if (extension === 'stl') {
    const geometry = useLoader(STLLoader, meshUrl)

    // Pour STL, on doit créer un mesh manuellement
    const material = new THREE.MeshStandardMaterial({
      color: 0x606060,
      flatShading: false,
      side: THREE.DoubleSide
    })
    model = new THREE.Mesh(geometry, material)

    // Calculer les normales pour un meilleur rendu
    geometry.computeVertexNormals()
  } else if (extension === 'ply') {
    const geometry = useLoader(PLYLoader, meshUrl)

    // Pour PLY, on doit créer un mesh manuellement
    const material = new THREE.MeshStandardMaterial({
      color: 0x606060,
      flatShading: false,
      side: THREE.DoubleSide,
      vertexColors: geometry.attributes.color ? true : false
    })
    model = new THREE.Mesh(geometry, material)

    // Calculer les normales pour un meilleur rendu
    geometry.computeVertexNormals()
  } else {
    // Format non supporté, fallback sur OBJ
    console.warn('Format non supporté:', extension, '- Tentative de chargement comme OBJ')
    model = useLoader(OBJLoader, meshUrl)
  }

  // Log des statistiques du modèle et fin du timer
  useEffect(() => {
    if (model) {
      const totalLabel = `TOTAL_LOAD_${filename}`
      const fetchParseLabel = `FETCH_AND_PARSE_${extension.toUpperCase()}_${filename}`

      // Terminer le timer de fetch+parse
      perf.end(fetchParseLabel)

      let vertexCount = 0
      let triangleCount = 0

      model.traverse((child) => {
        if (child.geometry) {
          const positions = child.geometry.attributes.position
          if (positions) {
            vertexCount += positions.count
          }
          if (child.geometry.index) {
            triangleCount += child.geometry.index.count / 3
          }
        }
      })

      console.log(`📊 [MODEL] ${filename}:`, {
        vertices: vertexCount.toLocaleString(),
        triangles: Math.floor(triangleCount).toLocaleString()
      })

      // Terminer le timer total et afficher le résumé
      perf.end(totalLabel)
      perf.summary()
    }
  }, [model, filename, extension])

  return (
    <Center>
      <primitive object={model} />
    </Center>
  )
}

export default MeshModel
