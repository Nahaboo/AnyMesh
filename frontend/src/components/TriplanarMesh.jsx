import { useMemo } from 'react'
import { Center } from '@react-three/drei'
import * as THREE from 'three'
import vertexShader from '../shaders/materials/triplanar/vertex.glsl'
import fragmentShader from '../shaders/materials/triplanar/fragment.glsl'

const textureLoader = new THREE.TextureLoader()

function loadTextures(type) {
  const path = `/textures/${type}`
  const colorMap = textureLoader.load(`${path}/color.jpg`)
  const normalMap = textureLoader.load(`${path}/normal.jpg`)
  const roughnessMap = textureLoader.load(`${path}/roughness.jpg`)

  ;[colorMap, normalMap, roughnessMap].forEach(t => {
    t.wrapS = t.wrapT = THREE.RepeatWrapping
  })

  // Normal map should be linear, not sRGB
  normalMap.colorSpace = THREE.LinearSRGBColorSpace
  roughnessMap.colorSpace = THREE.LinearSRGBColorSpace

  return { colorMap, normalMap, roughnessMap }
}

function TriplanarMesh({ model, presetId, visualConfig, proceduralConfig, uploadId }) {
  const processedModel = useMemo(() => {
    if (!model) return null

    const cloned = model.clone()

    const box = new THREE.Box3().setFromObject(cloned)
    const size = new THREE.Vector3()
    box.getSize(size)
    const diagonal = Math.sqrt(size.x * size.x + size.y * size.y + size.z * size.z) || 1

    const textureScale = (proceduralConfig.scale || 3.0) / diagonal
    const textures = loadTextures(proceduralConfig.type)

    cloned.traverse((child) => {
      if (child.isMesh) {
        if (child.geometry && !child.geometry.attributes.normal) {
          child.geometry.computeVertexNormals()
        }

        child.material = new THREE.ShaderMaterial({
          uniforms: {
            uColorMap: { value: textures.colorMap },
            uNormalMap: { value: textures.normalMap },
            uRoughnessMap: { value: textures.roughnessMap },
            uTextureScale: { value: textureScale },
            uBlendSharpness: { value: proceduralConfig.blendSharpness || 2.0 },
            uLightDir: { value: new THREE.Vector3(1, 1, 1).normalize() }
          },
          vertexShader,
          fragmentShader,
          side: THREE.DoubleSide,
          lights: false
        })
        child.material.needsUpdate = true
      }
    })

    return cloned
  }, [model, presetId, uploadId])

  if (!processedModel) return null

  return (
    <Center>
      <primitive object={processedModel} />
    </Center>
  )
}

export default TriplanarMesh
