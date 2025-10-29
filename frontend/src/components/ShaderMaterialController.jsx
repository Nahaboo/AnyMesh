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

    // Calculate bounding box to determine mesh scale for organic shaders
    let meshScale = 1.0
    if (isOrganicShader) {
      const box = new THREE.Box3().setFromObject(cloned)
      const size = new THREE.Vector3()
      box.getSize(size)
      // Use the diagonal of the bounding box as a reference scale
      meshScale = Math.sqrt(size.x * size.x + size.y * size.y + size.z * size.z)
      console.log(`[ShaderMaterialController] Mesh scale: ${meshScale.toFixed(2)}`)

      // Add mesh scale uniform for organic shaders
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
          materialConfig.vertexColors = false

          // Convert Mesh to Points for point cloud rendering
          const pointsMaterial = new THREE.ShaderMaterial(materialConfig)
          const points = new THREE.Points(child.geometry, pointsMaterial)

          // Copy transform from original mesh
          points.position.copy(child.position)
          points.rotation.copy(child.rotation)
          points.scale.copy(child.scale)

          // Mark for replacement
          nodesToReplace.push({ oldNode: child, newNode: points })
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
