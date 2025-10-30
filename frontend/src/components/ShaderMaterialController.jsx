import { useMemo, useRef } from 'react'
import { Center } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useMouseRaycast } from '../hooks/useMouseRaycast'

/**
 * Adds barycentric coordinates to a geometry for wireframe rendering
 * Each vertex gets coordinates (1,0,0), (0,1,0), or (0,0,1) based on its position in the triangle
 */
function addBarycentricCoordinates(geometry) {
  const position = geometry.attributes.position
  const count = position.count
  const barycentric = new Float32Array(count * 3)

  for (let i = 0; i < count; i += 3) {
    // First vertex of triangle: (1, 0, 0)
    barycentric[i * 3] = 1
    barycentric[i * 3 + 1] = 0
    barycentric[i * 3 + 2] = 0

    // Second vertex of triangle: (0, 1, 0)
    barycentric[(i + 1) * 3] = 0
    barycentric[(i + 1) * 3 + 1] = 1
    barycentric[(i + 1) * 3 + 2] = 0

    // Third vertex of triangle: (0, 0, 1)
    barycentric[(i + 2) * 3] = 0
    barycentric[(i + 2) * 3 + 1] = 0
    barycentric[(i + 2) * 3 + 2] = 1
  }

  geometry.setAttribute('barycentric', new THREE.BufferAttribute(barycentric, 3))
}

/**
 * ShaderMaterialController - Applies custom GLSL shaders to 3D models
 *
 * @param {Object} model - The loaded 3D model (Three.js Object3D)
 * @param {Object} shader - Shader configuration from shaders/materials/
 * @param {Object} params - Runtime parameters for shader uniforms (optional)
 * @param {number} uploadId - Trigger re-render when model changes
 */
function ShaderMaterialController({ model, shader, params = {}, uploadId }) {
  // Extract shader ID for stable dependency
  const shaderId = shader?.id
  // Serialize params for stable dependency comparison
  const paramsKey = JSON.stringify(params)

  // Store reference to processed model for animation updates
  const processedModelRef = useRef(null)

  // Check if this is an organic shader that needs mouse interaction
  const isOrganicShader = shaderId?.startsWith('organic-')

  // Check if this shader needs mesh scale calculation
  const needsMeshScale = isOrganicShader || shaderId === 'point-cloud'

  // Perform raycasting for mouse interaction (throttled to 50ms)
  const mouseWorldPosition = useMouseRaycast(processedModelRef.current, isOrganicShader, 50)

  // Process model with custom shader
  const processedModel = useMemo(() => {
    if (!model || !shader) return null

    // Log only when shader is applied (useMemo ensures this runs only on dependency change)
    console.log(`[ShaderMaterialController] Applying shader: ${shader.name}`)

    // Clone the model to avoid modifying the original
    const cloned = model.clone()

    // Prepare uniforms with default values + runtime overrides
    const uniforms = {}
    Object.entries(shader.uniforms).forEach(([key, config]) => {
      // Use runtime param if provided, otherwise use default value
      const value = params[key] !== undefined ? params[key] : config.value

      // Convert value to Three.js uniform format
      if (config.type === 'color') {
        // Color: array [r, g, b] -> THREE.Color
        uniforms[key] = { value: new THREE.Color(...value) }
      } else if (config.type === 'vec3') {
        // Vec3: array [x, y, z] -> THREE.Vector3
        uniforms[key] = { value: new THREE.Vector3(...value) }
      } else if (config.type === 'vec2') {
        // Vec2: array [x, y] -> THREE.Vector2
        uniforms[key] = { value: new THREE.Vector2(...value) }
      } else {
        // Scalar types (int, float, bool)
        uniforms[key] = { value }
      }
    })

    // Verbose logging for debug (comment out in production)
    // console.log('[ShaderMaterialController] Uniforms:', uniforms)

    // Calculate bounding box to determine mesh scale for shaders that need it
    let meshScale = 1.0
    if (needsMeshScale) {
      const box = new THREE.Box3().setFromObject(cloned)
      const size = new THREE.Vector3()
      box.getSize(size)
      // Use the diagonal of the bounding box as a reference scale
      meshScale = Math.sqrt(size.x * size.x + size.y * size.y + size.z * size.z)
      console.log(`[ShaderMaterialController] Mesh scale: ${meshScale.toFixed(2)}`)

      // Add mesh scale uniform
      uniforms.uMeshScale = { value: meshScale }
    }

    // Apply shader material to all meshes in the model
    const nodesToReplace = []

    cloned.traverse((child) => {
      if (child.isMesh) {
        // Ensure geometry has normals
        if (child.geometry && !child.geometry.attributes.normal) {
          console.log('[ShaderMaterialController] Computing normals for geometry')
          child.geometry.computeVertexNormals()
        }

        // Add barycentric coordinates for wireframe shader
        if (shaderId === 'organic-wireframe') {
          addBarycentricCoordinates(child.geometry)
        }

        // Create ShaderMaterial with custom GLSL
        const materialConfig = {
          uniforms: uniforms,
          vertexShader: shader.vertexShader,
          fragmentShader: shader.fragmentShader,
          side: THREE.DoubleSide,
          lights: false, // We handle lighting in the shader
          transparent: shaderId === 'organic-wireframe' || shaderId === 'point-cloud', // Enable transparency
          depthWrite: shaderId !== 'organic-wireframe' // Disable depth write for wireframe
        }

        // Special config for point cloud shader
        if (shaderId === 'point-cloud') {
          materialConfig.transparent = true
          materialConfig.depthWrite = true

          console.log(`[ShaderMaterialController] Creating point cloud with two separate layers`)

          // Get original vertex count
          const originalCount = child.geometry.attributes.position.count

          // Auto LOD: progressive density reduction based on vertex count
          let autoDensity = 1.0
          if (originalCount < 50000) {
            autoDensity = 1.0 // Small models: 100%
          } else if (originalCount < 100000) {
            autoDensity = 0.8 // Medium models: 80%
          } else if (originalCount < 150000) {
            autoDensity = 0.6 // Large models: 60%
          } else if (originalCount < 300000) {
            autoDensity = 0.4 // Very large models: 40%
          } else if (originalCount < 500000) {
            autoDensity = 0.25 // Huge models: 25%
          } else if (originalCount < 1000000) {
            autoDensity = 0.15 // Massive models: 15%
          } else {
            autoDensity = 0.1 // Ultra massive models: 10%
          }

          if (autoDensity < 1.0) {
            console.log(`[ShaderMaterialController] Auto LOD: ${originalCount} vertices → ${(autoDensity * 100).toFixed(0)}% density`)
          }

          // Get point density from params (default to auto-calculated density)
          const pointDensity = params.uPointDensity !== undefined ? params.uPointDensity : autoDensity

          // Update the uniform to reflect the actual density being used (for debug panel sync)
          if (uniforms.uPointDensity) {
            uniforms.uPointDensity.value = pointDensity
          }

          // Subsample geometry if density < 1.0
          let geometryToUse = child.geometry
          if (pointDensity < 1.0) {
            const originalGeometry = child.geometry
            const originalCount = originalGeometry.attributes.position.count
            const targetCount = Math.max(1, Math.floor(originalCount * pointDensity))

            // Create subsampled geometry
            const subsampledGeometry = new THREE.BufferGeometry()
            const step = Math.max(1, Math.floor(originalCount / targetCount))

            const positions = []
            const normals = []

            for (let i = 0; i < originalCount; i += step) {
              const pos = originalGeometry.attributes.position
              positions.push(pos.getX(i), pos.getY(i), pos.getZ(i))

              if (originalGeometry.attributes.normal) {
                const norm = originalGeometry.attributes.normal
                normals.push(norm.getX(i), norm.getY(i), norm.getZ(i))
              }
            }

            subsampledGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
            if (normals.length > 0) {
              subsampledGeometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3))
            }

            geometryToUse = subsampledGeometry
            console.log(`[ShaderMaterialController] Subsampled from ${originalCount} to ${positions.length / 3} vertices (${(pointDensity * 100).toFixed(0)}%)`)
          }

          // Create static layer material
          const staticMaterialConfig = { ...materialConfig }
          staticMaterialConfig.uniforms = {
            ...staticMaterialConfig.uniforms,
            uIsStatic: { value: 1.0 }
          }
          const staticMaterial = new THREE.ShaderMaterial(staticMaterialConfig)
          const staticPoints = new THREE.Points(geometryToUse.clone(), staticMaterial)

          // Create dynamic layer material
          const dynamicMaterialConfig = { ...materialConfig }
          dynamicMaterialConfig.uniforms = {
            ...dynamicMaterialConfig.uniforms,
            uIsStatic: { value: 0.0 }
          }
          const dynamicMaterial = new THREE.ShaderMaterial(dynamicMaterialConfig)
          const dynamicPoints = new THREE.Points(geometryToUse.clone(), dynamicMaterial)

          // Create a group to hold both layers
          const pointCloudGroup = new THREE.Group()
          pointCloudGroup.add(staticPoints)
          pointCloudGroup.add(dynamicPoints)

          // Copy transform from original mesh
          pointCloudGroup.position.copy(child.position)
          pointCloudGroup.rotation.copy(child.rotation)
          pointCloudGroup.scale.copy(child.scale)

          const vertexCount = geometryToUse.attributes.position.count
          console.log(`[ShaderMaterialController] Created point cloud group with ${vertexCount} vertices × 2 layers (total ${vertexCount * 2} points)`)

          // Mark for replacement
          nodesToReplace.push({ oldNode: child, newNode: pointCloudGroup })
        } else {
          child.material = new THREE.ShaderMaterial(materialConfig)
          child.material.needsUpdate = true
        }
      }
    })

    // Replace meshes with points for point-cloud shader
    nodesToReplace.forEach(({ oldNode, newNode }) => {
      if (oldNode.parent) {
        oldNode.parent.add(newNode)
        oldNode.parent.remove(oldNode)
      }
    })

    return cloned
  }, [model, shaderId, paramsKey, uploadId])

  // Update reference when processed model changes
  processedModelRef.current = processedModel

  // Animation loop: update uTime and uMousePosition uniforms every frame
  useFrame((state) => {
    if (!processedModel || !shader) return

    processedModel.traverse((child) => {
      // Handle both Mesh and Points objects
      const hasMaterial = (child.isMesh || child.isPoints) && child.material && child.material.uniforms

      if (hasMaterial) {
        const uniforms = child.material.uniforms

        // Update time uniform for animation
        if (uniforms.uTime) {
          uniforms.uTime.value = state.clock.elapsedTime
          // Debug log once per second
          if (shaderId === 'point-cloud' && Math.floor(state.clock.elapsedTime) % 5 === 0 && state.clock.elapsedTime % 1 < 0.1) {
            console.log(`[ShaderMaterialController] uTime updated: ${state.clock.elapsedTime.toFixed(2)}`)
          }
        }

        // Update mouse position uniform for interaction
        if (uniforms.uMousePosition && mouseWorldPosition) {
          uniforms.uMousePosition.value.set(...mouseWorldPosition)
        }
      }
    })
  })

  if (!processedModel) {
    console.warn('[ShaderMaterialController] No model or shader provided')
    return null
  }

  return (
    <Center>
      <primitive object={processedModel} />
    </Center>
  )
}

export default ShaderMaterialController
