import { useMemo } from 'react'
import { Center } from '@react-three/drei'
import * as THREE from 'three'

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

    // Apply shader material to all meshes in the model
    cloned.traverse((child) => {
      if (child.isMesh) {
        // Ensure geometry has normals
        if (child.geometry && !child.geometry.attributes.normal) {
          console.log('[ShaderMaterialController] Computing normals for geometry')
          child.geometry.computeVertexNormals()
        }

        // Create ShaderMaterial with custom GLSL
        child.material = new THREE.ShaderMaterial({
          uniforms: uniforms,
          vertexShader: shader.vertexShader,
          fragmentShader: shader.fragmentShader,
          side: THREE.DoubleSide,
          lights: false, // We handle lighting in the shader
          transparent: false
        })

        child.material.needsUpdate = true
      }
    })

    return cloned
  }, [model, shaderId, paramsKey, uploadId])

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
