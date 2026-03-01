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
import TriplanarMesh from './TriplanarMesh'
import { getMaterialShader } from '../shaders/materials'
import { API_BASE_URL } from '../utils/api'
import glassVertexShader from '../shaders/materials/triplanar/vertex.glsl'
import glassFragmentShader from '../shaders/materials/triplanar/glass.glsl'
import { disposeObject } from '../utils/dispose'

/**
 * QualityEdgeOverlay - Renders edge lines as a LineSegments overlay.
 */
function QualityEdgeOverlay({ positions, color }) {
  const posArray = useMemo(() => new Float32Array(positions), [positions])
  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[posArray, 3]}
        />
      </bufferGeometry>
      <lineBasicMaterial
        color={color}
        linewidth={2}
        depthTest
        transparent
        opacity={0.9}
        polygonOffset
        polygonOffsetFactor={-1}
        polygonOffsetUnits={-1}
      />
    </lineSegments>
  )
}

/**
 * RenderModeController - Handles different rendering modes for 3D models
 * Modes: solid, wireframe, normal (normal map visualization), smooth, textured, shader:*
 */
function RenderModeController({ filename, isGenerated = false, isSimplified = false, isRetopologized = false, isSegmented = false, isCompared = false, isQuality = false, renderMode = 'solid', shaderParams = {}, uploadId, materialPreset = null, qualityOverlays = null }) {
  const [needsUpdate, setNeedsUpdate] = useState(0)
  const prevModelRef = useRef(null)
  const originalMaterialsRef = useRef(new Map())

  // Check if renderMode is a custom shader (format: "shader:toon")
  const isShaderMode = renderMode.startsWith('shader:')
  const shaderId = isShaderMode ? renderMode.split(':')[1] : null
  const shaderConfig = shaderId ? getMaterialShader(shaderId) : null

  // Q4: Build URL - handle different mesh sources (utilise API_BASE_URL configurable)
  // Add uploadId as cache-busting parameter to force browser to reload file
  let meshUrl
  if (isQuality) {
    meshUrl = `${API_BASE_URL}/mesh/quality/${filename}?v=${uploadId || Date.now()}`
  } else if (isCompared) {
    meshUrl = `${API_BASE_URL}/mesh/compared/${filename}?v=${uploadId || Date.now()}`
  } else if (isSegmented) {
    meshUrl = `${API_BASE_URL}/mesh/segmented/${filename}?v=${uploadId || Date.now()}`
  } else if (isRetopologized) {
    meshUrl = `${API_BASE_URL}/mesh/retopo/${filename}?v=${uploadId || Date.now()}`
  } else if (isSimplified) {
    meshUrl = `${API_BASE_URL}/mesh/output/${filename}?v=${uploadId || Date.now()}`
  } else if (isGenerated) {
    meshUrl = `${API_BASE_URL}/mesh/generated/${filename}?v=${uploadId || Date.now()}`
  } else {
    meshUrl = `${API_BASE_URL}/mesh/input/${filename}?v=${uploadId || Date.now()}`
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
    // Store original materials on first load (keyed by mesh name or index)
    if (originalMaterialsRef.current.size === 0) {
      let meshIdx = 0
      gltf.scene.traverse((child) => {
        if (child.isMesh && child.material) {
          const key = child.name || `mesh_${meshIdx}`
          originalMaterialsRef.current.set(key, child.material.clone())
          meshIdx++
        }
      })
    }
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

    // Dispose le clone précédent avant d'en créer un nouveau
    if (prevModelRef.current) {
      disposeObject(prevModelRef.current)
      prevModelRef.current = null
    }

    console.log(`[RenderModeController] Processing model with mode: ${renderMode}`)

    // Clone the model to avoid modifying the original
    // For GLB: deep-clone materials so original textures are preserved
    const cloned = loadedModel.clone()
    cloned.traverse((child) => {
      if (child.isMesh && child.material) {
        child.material = child.material.clone()
      }
    })

    // Apply render mode to all meshes
    let cloneMeshIdx = 0
    cloned.traverse((child) => {
      if (child.isMesh) {
        const meshKey = child.name || `mesh_${cloneMeshIdx}`
        cloneMeshIdx++
        // Store original geometry for smooth mode
        if (!child.userData.originalGeometry) {
          child.userData.originalGeometry = child.geometry.clone()
        }

        // Ensure all geometries have normals computed on load
        if (child.geometry && !child.geometry.attributes.normal) {
          console.log('[RenderModeController] Computing normals on initial load')
          child.geometry.computeVertexNormals()
        }

        // Material preset override (PBR material from physics presets)
        if (materialPreset?.visual) {
          const v = materialPreset.visual
          if (v.transparent) {
            // Glass: custom shader for smooth rendering
            child.material = new THREE.ShaderMaterial({
              vertexShader: glassVertexShader,
              fragmentShader: glassFragmentShader,
              transparent: true,
              depthWrite: false,
              side: THREE.FrontSide,
              lights: false
            })
          } else {
            child.material = new THREE.MeshStandardMaterial({
              color: v.color,
              metalness: v.metalness,
              roughness: v.roughness,
              opacity: v.opacity,
              side: THREE.DoubleSide,
              envMapIntensity: 1.0
            })
          }
          child.material.needsUpdate = true
          return
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

          case 'textured': {
            // Textured mode - restore original materials from GLB/GLTF
            const originalMat = originalMaterialsRef.current.get(meshKey)
            if (originalMat && (originalMat.map || originalMat.normalMap)) {
              child.material = originalMat.clone()
              child.material.side = THREE.DoubleSide
              console.log('[RenderModeController] Applied TEXTURED mode (restored original material with textures)')
            } else {
              // No saved material or no texture — fallback
              child.material = new THREE.MeshStandardMaterial({
                color: DEFAULT_COLOR,
                side: THREE.DoubleSide,
                flatShading: false,
                metalness: 0.1,
                roughness: 0.8
              })
              console.log('[RenderModeController] Applied TEXTURED mode (no texture found, using default material)')
            }
            break
          }

          default:
            break
        }

        child.material.needsUpdate = true
      }
    })

    prevModelRef.current = cloned
    return cloned
  }, [loadedModel, renderMode, uploadId, needsUpdate, materialPreset])

  // Cleanup au démontage du composant
  useEffect(() => {
    return () => {
      if (prevModelRef.current) {
        disposeObject(prevModelRef.current)
        prevModelRef.current = null
      }
    }
  }, [])

  // Reset original materials cache when file changes
  useEffect(() => {
    originalMaterialsRef.current = new Map()
  }, [meshUrl])

  // Force re-render when render mode changes
  useEffect(() => {
    console.log(`[RenderModeController] Render mode changed to: ${renderMode}`)
    setNeedsUpdate(prev => prev + 1)
  }, [renderMode])

  // If procedural material preset is active, use tri-planar shader
  if (materialPreset?.procedural) {
    return (
      <TriplanarMesh
        model={loadedModel}
        presetId={materialPreset.id}
        visualConfig={materialPreset.visual}
        proceduralConfig={materialPreset.procedural}
        uploadId={uploadId}
      />
    )
  }

  // If shader mode is active, delegate to ShaderMaterialController
  if (isShaderMode && shaderConfig && !materialPreset) {
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
      <group>
        <primitive object={processedModel} />
        {/* Quality edge overlays rendered inside same group to match mesh transform */}
        {qualityOverlays && qualityOverlays.length > 0 && qualityOverlays.map((overlay, i) => (
          overlay.positions && overlay.positions.length > 0 ? (
            <QualityEdgeOverlay
              key={`${overlay.type}-${i}`}
              positions={overlay.positions}
              color={overlay.color}
            />
          ) : null
        ))}
      </group>
    </Center>
  )
}

export default RenderModeController
