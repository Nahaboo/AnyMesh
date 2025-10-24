import { useEffect, useMemo, useRef, useState } from 'react'
import { useLoader } from '@react-three/fiber'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader'
import { Center } from '@react-three/drei'
import * as THREE from 'three'

/**
 * RenderModeController - Handles different rendering modes for 3D models
 * Modes: solid, wireframe, normal (normal map visualization), smooth
 */
function RenderModeController({ filename, isGenerated = false, isSimplified = false, renderMode = 'solid', uploadId }) {
  const [needsUpdate, setNeedsUpdate] = useState(0)

  // Build URL - handle simplified meshes from /mesh/output
  let meshUrl
  if (isSimplified) {
    meshUrl = `http://localhost:8000/mesh/output/${filename}`
  } else if (isGenerated) {
    meshUrl = `http://localhost:8000/mesh/generated/${filename}`
  } else {
    meshUrl = `http://localhost:8000/mesh/input/${filename}`
  }

  // Determine file format (with safety check)
  const extension = filename ? filename.split('.').pop().toLowerCase() : 'obj'

  // Light blue color for default rendering
  const DEFAULT_COLOR = 0xb3d9ff // Light blue

  // Load model based on format
  let loadedModel

  if (extension === 'obj') {
    loadedModel = useLoader(OBJLoader, meshUrl)
  } else if (extension === 'gltf' || extension === 'glb') {
    const gltf = useLoader(GLTFLoader, meshUrl)
    loadedModel = gltf.scene
  } else if (extension === 'stl') {
    const geometry = useLoader(STLLoader, meshUrl)
    const hasNormals = geometry.attributes.normal !== undefined

    const material = new THREE.MeshStandardMaterial({
      color: DEFAULT_COLOR,
      flatShading: false,
      side: THREE.DoubleSide,
      metalness: 0.1,
      roughness: 0.8
    })
    loadedModel = new THREE.Mesh(geometry, material)

    if (!hasNormals) {
      geometry.computeVertexNormals()
    }
  } else if (extension === 'ply') {
    const geometry = useLoader(PLYLoader, meshUrl)
    const hasNormals = geometry.attributes.normal !== undefined

    const material = new THREE.MeshStandardMaterial({
      color: DEFAULT_COLOR,
      flatShading: false,
      side: THREE.DoubleSide,
      vertexColors: geometry.attributes.color ? true : false,
      metalness: 0.1,
      roughness: 0.8
    })
    loadedModel = new THREE.Mesh(geometry, material)

    if (!hasNormals) {
      geometry.computeVertexNormals()
    }
  } else {
    // Fallback to OBJ
    loadedModel = useLoader(OBJLoader, meshUrl)
  }

  // Clone and process model based on render mode
  const processedModel = useMemo(() => {
    if (!loadedModel) return null

    console.log(`[RenderModeController] Processing model with mode: ${renderMode}`)

    // Clone the model to avoid modifying the original
    const cloned = loadedModel.clone()

    // Apply render mode to all meshes
    cloned.traverse((child) => {
      if (child.isMesh) {
        // Store original geometry for smooth mode
        if (!child.userData.originalGeometry) {
          child.userData.originalGeometry = child.geometry.clone()
        }

        // Ensure all geometries have normals computed on load
        if (child.geometry && !child.geometry.attributes.normal) {
          console.log('[RenderModeController] Computing normals on initial load')
          child.geometry.computeVertexNormals()
        }

        switch (renderMode) {
          case 'solid':
            child.material = new THREE.MeshStandardMaterial({
              color: DEFAULT_COLOR,
              side: THREE.DoubleSide,
              wireframe: false,
              flatShading: false,
              metalness: 0.1,
              roughness: 0.8
            })
            console.log('[RenderModeController] Applied SOLID mode')
            break

          case 'wireframe':
            child.material = new THREE.MeshStandardMaterial({
              color: DEFAULT_COLOR,
              side: THREE.DoubleSide,
              wireframe: true,
              metalness: 0.1,
              roughness: 0.8
            })
            console.log('[RenderModeController] Applied WIREFRAME mode')
            break

          case 'normal':
            // Normals are already computed on load
            child.material = new THREE.MeshNormalMaterial({
              side: THREE.DoubleSide,
              flatShading: false
            })
            console.log('[RenderModeController] Applied NORMAL mode')
            break

          case 'flat':
            // Flat shading mode - shows faceted appearance
            child.material = new THREE.MeshStandardMaterial({
              color: DEFAULT_COLOR,
              side: THREE.DoubleSide,
              wireframe: false,
              flatShading: true, // This creates the faceted look
              metalness: 0.1,
              roughness: 0.8
            })
            console.log('[RenderModeController] Applied FLAT mode')
            break

          case 'smooth':
            // Smooth mode - recompute normals for extra smoothness
            if (child.geometry && child.geometry.attributes.position) {
              const newGeometry = child.userData.originalGeometry.clone()
              newGeometry.deleteAttribute('normal')
              newGeometry.computeVertexNormals()
              child.geometry = newGeometry
            }

            child.material = new THREE.MeshStandardMaterial({
              color: DEFAULT_COLOR,
              side: THREE.DoubleSide,
              flatShading: false,
              metalness: 0.1,
              roughness: 0.8
            })
            console.log('[RenderModeController] Applied SMOOTH mode (normals recomputed)')
            break

          default:
            break
        }

        child.material.needsUpdate = true
      }
    })

    return cloned
  }, [loadedModel, renderMode, uploadId, needsUpdate])

  // Force re-render when render mode changes
  useEffect(() => {
    console.log(`[RenderModeController] Render mode changed to: ${renderMode}`)
    setNeedsUpdate(prev => prev + 1)
  }, [renderMode])

  if (!processedModel) return null

  return (
    <Center>
      <primitive object={processedModel} />
    </Center>
  )
}

export default RenderModeController
