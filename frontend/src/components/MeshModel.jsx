import { useEffect, useRef } from 'react'
import { useLoader, useFrame } from '@react-three/fiber'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader'
import { Center } from '@react-three/drei'
import * as THREE from 'three'
import perf from '../utils/performance'

// Créer un loader personnalisé pour mesurer les performances
class InstrumentedGLTFLoader extends GLTFLoader {
  constructor() {
    super()
    this.loadStart = 0
    this.fetchEnd = 0
  }

  load(url, onLoad, onProgress, onError) {
    this.loadStart = performance.now()

    // Wrapper pour mesurer le temps de chargement
    const measureOnLoad = (gltf) => {
      const loadEnd = performance.now()
      const loadDuration = loadEnd - this.loadStart

      // Analyser la géométrie
      let totalVertices = 0
      let totalTriangles = 0
      let meshCount = 0

      gltf.scene.traverse((child) => {
        if (child.isMesh) {
          meshCount++
          if (child.geometry) {
            const positions = child.geometry.attributes.position
            if (positions) {
              totalVertices += positions.count
            }
            if (child.geometry.index) {
              totalTriangles += child.geometry.index.count / 3
            }
          }
        }
      })

      // Vérifier Draco compression (important pour le debug)
      const hasDraco = gltf.parser?.json?.extensionsUsed?.includes('KHR_draco_mesh_compression') || false

      // Log condensé avec toutes les infos importantes
      console.log(`🟢 [GLTFLoader] Loaded in ${loadDuration.toFixed(2)}ms | ${totalVertices.toLocaleString()} vertices, ${Math.floor(totalTriangles).toLocaleString()} triangles${hasDraco ? ' | Draco: YES' : ''}`)

      onLoad(gltf)
    }

    // Appeler la méthode load() originale avec notre wrapper
    super.load(url, measureOnLoad, onProgress, onError)
  }
}

/**
 * Composant qui charge et affiche un fichier 3D (OBJ, GLTF, GLB, STL, PLY)
 *
 * @param {string} filename - Nom du fichier à charger
 * @param {boolean} isGenerated - true si le fichier provient de /mesh/generated/, false pour /mesh/input/
 */
function MeshModel({ filename, isGenerated = false }) {
  // Construire l'URL du fichier sur le backend
  const meshUrl = isGenerated
    ? `http://localhost:8000/mesh/generated/${filename}`
    : `http://localhost:8000/mesh/input/${filename}`

  // Déterminer le format du fichier
  const extension = filename.split('.').pop().toLowerCase()

  // IMPORTANT: Démarrer le timer AVANT useLoader (qui s'exécute de manière synchrone)
  // On utilise une variable globale pour stocker le timestamp de début
  if (!window.__meshLoadStart) {
    window.__meshLoadStart = performance.now()
    perf.reset()
    console.log(`🔵 [MeshModel] Loading: ${filename} (${extension}) from ${meshUrl}`)
  }

  // Charger le modèle selon le format
  // Note: useLoader gère le téléchargement réseau + parsing de manière bloquante
  let model

  if (extension === 'obj') {
    model = useLoader(OBJLoader, meshUrl)
  } else if (extension === 'gltf' || extension === 'glb') {
    const gltf = useLoader(InstrumentedGLTFLoader, meshUrl)
    model = gltf.scene

    // Stocker le temps de fin du loader pour calculer le délai avant le rendu
    window.__loaderEndTime = performance.now()
  } else if (extension === 'stl') {
    const geometry = useLoader(STLLoader, meshUrl)

    // STL ne contient jamais de normales dans le fichier
    const hasNormals = geometry.attributes.normal !== undefined

    // Pour STL, on doit créer un mesh manuellement
    const material = new THREE.MeshStandardMaterial({
      color: 0x606060,
      flatShading: !hasNormals, // Utiliser flat shading si pas de normales
      side: THREE.DoubleSide
    })
    model = new THREE.Mesh(geometry, material)

    // NE calculer les normales QUE si elles n'existent pas
    // ATTENTION: computeVertexNormals() est TRÈS coûteux sur de gros meshes
    if (!hasNormals) {
      console.warn('⚠️ [MeshModel] STL sans normales, calcul en cours (peut être lent)...')
      const computeStart = performance.now()
      geometry.computeVertexNormals()
      const computeDuration = performance.now() - computeStart
      console.log(`🟡 [MeshModel] Normals computed in ${computeDuration.toFixed(2)}ms`)
    }
  } else if (extension === 'ply') {
    const geometry = useLoader(PLYLoader, meshUrl)

    // Vérifier si le fichier PLY contient déjà des normales
    const hasNormals = geometry.attributes.normal !== undefined

    // Pour PLY, on doit créer un mesh manuellement
    const material = new THREE.MeshStandardMaterial({
      color: 0x606060,
      flatShading: !hasNormals, // Utiliser flat shading si pas de normales
      side: THREE.DoubleSide,
      vertexColors: geometry.attributes.color ? true : false
    })
    model = new THREE.Mesh(geometry, material)

    // NE calculer les normales QUE si elles n'existent pas
    // ATTENTION: computeVertexNormals() est TRÈS coûteux sur de gros meshes (plusieurs secondes/minutes)
    if (!hasNormals) {
      console.warn('⚠️ [MeshModel] PLY sans normales, calcul en cours (peut être lent)...')
      const computeStart = performance.now()
      geometry.computeVertexNormals()
      const computeDuration = performance.now() - computeStart
      console.log(`🟡 [MeshModel] Normals computed in ${computeDuration.toFixed(2)}ms`)
    }
  } else {
    // Format non supporté, fallback sur OBJ
    console.warn('Format non supporté:', extension, '- Tentative de chargement comme OBJ')
    model = useLoader(OBJLoader, meshUrl)
  }

  // Log des statistiques du modèle et fin du timer
  // IMPORTANT: Ce useEffect s'exécute APRÈS que le modèle soit chargé ET rendu
  useEffect(() => {
    if (model && window.__meshLoadStart) {
      // Calculer les statistiques du modèle
      let vertexCount = 0
      let triangleCount = 0
      let meshCount = 0

      model.traverse((child) => {
        if (child.geometry) {
          meshCount++
          const positions = child.geometry.attributes.position
          if (positions) {
            vertexCount += positions.count
          }
          if (child.geometry.index) {
            triangleCount += child.geometry.index.count / 3
          }
        }
      })

      if (meshCount === 0) {
        console.error('❌ [MeshModel] No mesh found in model!')
      }

      // Attendre le prochain frame pour s'assurer que le rendu est terminé
      requestAnimationFrame(() => {
        const loadEndTime = performance.now()
        const totalDuration = loadEndTime - window.__meshLoadStart

        const color = totalDuration < 1000 ? '🟢' : totalDuration < 5000 ? '🟡' : '🔴'
        console.log(`${color} [MeshModel] Rendered ${filename}: ${totalDuration.toFixed(2)}ms total (${vertexCount.toLocaleString()} vertices, ${Math.floor(triangleCount).toLocaleString()} triangles, ${meshCount} mesh${meshCount > 1 ? 'es' : ''})`)

        // Nettoyer
        window.__meshLoadStart = null
      })
    }
  }, [model, filename])

  // Mesurer le temps de rendu du composant Center
  const renderRef = useRef(null)
  const frameCountRef = useRef(0)
  const firstFrameTimeRef = useRef(null)

  // Mesurer le premier frame (silencieux, utilisé uniquement pour la performance)
  useFrame(() => {
    if (frameCountRef.current === 0 && !firstFrameTimeRef.current) {
      firstFrameTimeRef.current = performance.now()
      // Pas de log, c'est déjà loggé dans le useEffect final
    }
    if (frameCountRef.current < 5) {
      frameCountRef.current++
    }
  })

  return (
    <Center ref={renderRef}>
      <primitive object={model} />
    </Center>
  )
}

export default MeshModel
