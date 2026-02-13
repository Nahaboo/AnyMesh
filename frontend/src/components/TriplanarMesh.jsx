import { useEffect, useMemo, useRef } from 'react'
import { Center } from '@react-three/drei'
import * as THREE from 'three'
import vertexShader from '../shaders/materials/triplanar/vertex.glsl'
import fragmentShader from '../shaders/materials/triplanar/fragment.glsl'
import { disposeObject } from '../utils/dispose'

const textureLoader = new THREE.TextureLoader()

function loadTextures(proceduralConfig) {
  if (proceduralConfig.customTextureUrls) {
    // AI-generated texture: load color from URL, use flat defaults for normal/roughness
    const colorMap = textureLoader.load(proceduralConfig.customTextureUrls.color)
    colorMap.wrapS = colorMap.wrapT = THREE.RepeatWrapping

    const normalData = new Uint8Array([128, 128, 255, 255])
    const normalMap = new THREE.DataTexture(normalData, 1, 1, THREE.RGBAFormat)
    normalMap.wrapS = normalMap.wrapT = THREE.RepeatWrapping
    normalMap.colorSpace = THREE.LinearSRGBColorSpace
    normalMap.needsUpdate = true

    const roughData = new Uint8Array([128, 128, 128, 255])
    const roughnessMap = new THREE.DataTexture(roughData, 1, 1, THREE.RGBAFormat)
    roughnessMap.wrapS = roughnessMap.wrapT = THREE.RepeatWrapping
    roughnessMap.colorSpace = THREE.LinearSRGBColorSpace
    roughnessMap.needsUpdate = true

    return { colorMap, normalMap, roughnessMap }
  }

  // Existing preset path
  const path = `/textures/${proceduralConfig.type}`
  const colorMap = textureLoader.load(`${path}/color.jpg`)
  const normalMap = textureLoader.load(`${path}/normal.jpg`)
  const roughnessMap = textureLoader.load(`${path}/roughness.jpg`)

  ;[colorMap, normalMap, roughnessMap].forEach(t => {
    t.wrapS = t.wrapT = THREE.RepeatWrapping
  })

  normalMap.colorSpace = THREE.LinearSRGBColorSpace
  roughnessMap.colorSpace = THREE.LinearSRGBColorSpace

  return { colorMap, normalMap, roughnessMap }
}

function TriplanarMesh({ model, presetId, visualConfig, proceduralConfig, uploadId }) {
  const prevModelRef = useRef(null)

  const processedModel = useMemo(() => {
    if (!model) return null

    // Dispose le clone précédent (géométries + matériaux + textures)
    if (prevModelRef.current) {
      disposeObject(prevModelRef.current)
      prevModelRef.current = null
    }

    const cloned = model.clone()

    const box = new THREE.Box3().setFromObject(cloned)
    const size = new THREE.Vector3()
    box.getSize(size)
    const diagonal = Math.sqrt(size.x * size.x + size.y * size.y + size.z * size.z) || 1

    const textureScale = (proceduralConfig.scale || 3.0) / diagonal
    const textures = loadTextures(proceduralConfig)

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

    prevModelRef.current = cloned
    return cloned
  }, [model, presetId, uploadId])

  // Cleanup au démontage
  useEffect(() => {
    return () => {
      if (prevModelRef.current) {
        disposeObject(prevModelRef.current)
        prevModelRef.current = null
      }
    }
  }, [])

  if (!processedModel) return null

  return (
    <Center>
      <primitive object={processedModel} />
    </Center>
  )
}

export default TriplanarMesh
