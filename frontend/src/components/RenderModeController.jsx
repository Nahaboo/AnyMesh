import { useEffect, useMemo, useRef, useState } from 'react'
import { useLoader } from '@react-three/fiber'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader'
import { Center } from '@react-three/drei'
import * as THREE from 'three'
import { TextureLoader } from 'three'
import ShaderMaterialController from './ShaderMaterialController'
import { getMaterialShader } from '../shaders/materials'

/**
 * RenderModeController - Handles different rendering modes for 3D models
 * Modes: solid, wireframe, normal (normal map visualization), smooth, textured, shader:*
 */
function RenderModeController({ filename, isGenerated = false, isSimplified = false, isRetopologized = false, isSegmented = false, renderMode = 'solid', shaderParams = {}, uploadId }) {
  const [needsUpdate, setNeedsUpdate] = useState(0)

  // Check if renderMode is a custom shader (format: "shader:toon")
  const isShaderMode = renderMode.startsWith('shader:')
  const shaderId = isShaderMode ? renderMode.split(':')[1] : null
  const shaderConfig = shaderId ? getMaterialShader(shaderId) : null

  // Build URL - handle different mesh sources
  // Add uploadId as cache-busting parameter to force browser to reload file
  let meshUrl
  if (isSegmented) {
    meshUrl = `http://localhost:8000/mesh/segmented/${filename}?v=${uploadId || Date.now()}`
  } else if (isRetopologized) {
    meshUrl = `http://localhost:8000/mesh/retopo/${filename}?v=${uploadId || Date.now()}`
  } else if (isSimplified) {
    meshUrl = `http://localhost:8000/mesh/output/${filename}?v=${uploadId || Date.now()}`
  } else if (isGenerated) {
    meshUrl = `http://localhost:8000/mesh/generated/${filename}?v=${uploadId || Date.now()}`
  } else {
    meshUrl = `http://localhost:8000/mesh/input/${filename}?v=${uploadId || Date.now()}`
  }

  // Determine file format (with safety check)
  const extension = filename ? filename.split('.').pop().toLowerCase() : 'obj'

  // Light blue color for default rendering
  const DEFAULT_COLOR = 0xb3d9ff // Light blue

  // Load matcap texture for solid and flat modes from frontend public folder
  //const matcapTexture = useLoader(TextureLoader, '/matcap/161B1F.png')
  const matcapTexture = useLoader(TextureLoader, '/matcap/A9A2A0.png')

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
            // Check if geometry has vertex colors (for segmented meshes)
            const hasVertexColors = child.geometry.attributes.color !== undefined

            if (hasVertexColors) {
              // Use MeshStandardMaterial with vertex colors enabled
              child.material = new THREE.MeshStandardMaterial({
                vertexColors: true,
                side: THREE.DoubleSide,
                flatShading: false,
                metalness: 0.1,
                roughness: 0.8
              })
              console.log('[RenderModeController] Applied SOLID mode with VERTEX COLORS (segmented mesh)')
            } else {
              // Use matcap for performance and uniform lighting
              child.material = new THREE.MeshMatcapMaterial({
                matcap: matcapTexture,
                side: THREE.DoubleSide,
                flatShading: false
              })
              console.log('[RenderModeController] Applied SOLID mode with matcap')
            }
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
            // Flat shading mode with matcap - shows faceted appearance
            // MeshMatcapMaterial doesn't support flatShading, so we need to modify geometry
            if (child.geometry && child.geometry.attributes.position) {
              // Clone geometry and compute flat normals (one normal per face)
              const flatGeometry = child.geometry.clone()
              flatGeometry.deleteAttribute('normal')

              // computeVertexNormals with non-indexed geometry creates flat shading
              // First, convert to non-indexed if needed
              if (flatGeometry.index !== null) {
                const nonIndexedGeometry = flatGeometry.toNonIndexed()
                child.geometry = nonIndexedGeometry
                child.geometry.computeVertexNormals()
              } else {
                child.geometry = flatGeometry
                child.geometry.computeVertexNormals()
              }
            }

            child.material = new THREE.MeshMatcapMaterial({
              matcap: matcapTexture,
              side: THREE.DoubleSide
            })
            console.log('[RenderModeController] Applied FLAT mode with matcap (faceted normals)')
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

          case 'textured':
            // Textured mode - preserve original materials and textures from GLB/GLTF
            // Don't replace the material, just ensure it renders properly
            if (!child.material.map && !child.material.normalMap) {
              // If no texture, apply a default material
              child.material = new THREE.MeshStandardMaterial({
                color: DEFAULT_COLOR,
                side: THREE.DoubleSide,
                flatShading: false,
                metalness: 0.1,
                roughness: 0.8
              })
              console.log('[RenderModeController] Applied TEXTURED mode (no texture found, using default material)')
            } else {
              // Material has textures, keep it as is but ensure DoubleSide
              child.material.side = THREE.DoubleSide
              console.log('[RenderModeController] Applied TEXTURED mode (preserving original material with textures)')
            }
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

  // If shader mode is active, delegate to ShaderMaterialController
  if (isShaderMode && shaderConfig) {
    // Only log once on shader change, not every frame
    // console.log(`[RenderModeController] Using custom shader: ${shaderConfig.name}`)
    return (
      <ShaderMaterialController
        model={loadedModel}
        shader={shaderConfig}
        params={shaderParams}
        uploadId={uploadId}
      />
    )
  }

  // Otherwise, use standard material processing
  if (!processedModel) return null

  return (
    <Center>
      <primitive object={processedModel} />
    </Center>
  )
}

export default RenderModeController
