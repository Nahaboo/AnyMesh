import { useMemo, useRef, useEffect, Suspense } from 'react'
import { useLoader } from '@react-three/fiber'
import { Physics, RigidBody, BallCollider, ConvexHullCollider } from '@react-three/rapier'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader'
import * as THREE from 'three'
import { API_BASE_URL } from '../utils/api'
import { disposeObject } from '../utils/dispose'
import glassVertexShader from '../shaders/materials/triplanar/vertex.glsl'
import glassFragmentShader from '../shaders/materials/triplanar/glass.glsl'

const textureLoader = new THREE.TextureLoader()

function loadTextures(proceduralConfig) {
  if (proceduralConfig.customTextureUrls) {
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

/** Subsample vertices to at most maxPoints for a simpler convex hull */
function subsampleVertices(positions, maxPoints) {
  const totalVertices = positions.length / 3
  if (totalVertices <= maxPoints) return new Float32Array(positions)

  const step = Math.ceil(totalVertices / maxPoints)
  const result = []
  for (let i = 0; i < totalVertices; i += step) {
    result.push(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2])
  }
  return new Float32Array(result)
}

/**
 * PhysicsMesh - Loads a mesh and wraps it in a dynamic RigidBody.
 * Uses a simplified ConvexHullCollider (max 256 vertices) for stable contacts.
 */
function PhysicsMesh({ filename, isGenerated, isSimplified, isRetopologized, isSegmented, density, restitution, damping, dropHeight, boundingBox, materialPreset, resetKey }) {
  const prevModelRef = useRef(null)
  const prevTexturesRef = useRef([])
  const rbRef = useRef(null)
  let meshUrl
  if (isSegmented) {
    meshUrl = `${API_BASE_URL}/mesh/segmented/${filename}`
  } else if (isRetopologized) {
    meshUrl = `${API_BASE_URL}/mesh/retopo/${filename}`
  } else if (isSimplified) {
    meshUrl = `${API_BASE_URL}/mesh/output/${filename}`
  } else if (isGenerated) {
    meshUrl = `${API_BASE_URL}/mesh/generated/${filename}`
  } else {
    meshUrl = `${API_BASE_URL}/mesh/input/${filename}`
  }

  const extension = filename.split('.').pop().toLowerCase()

  let model
  if (extension === 'obj') {
    model = useLoader(OBJLoader, meshUrl)
  } else if (extension === 'gltf' || extension === 'glb') {
    const gltf = useLoader(GLTFLoader, meshUrl)
    model = gltf.scene
  } else if (extension === 'stl') {
    const geometry = useLoader(STLLoader, meshUrl)
    const material = new THREE.MeshStandardMaterial({ color: 0x606060, side: THREE.DoubleSide })
    model = new THREE.Mesh(geometry, material)
  } else if (extension === 'ply') {
    const geometry = useLoader(PLYLoader, meshUrl)
    const material = new THREE.MeshStandardMaterial({
      color: 0x606060,
      side: THREE.DoubleSide,
      vertexColors: !!geometry.attributes.color
    })
    model = new THREE.Mesh(geometry, material)
  } else {
    model = useLoader(OBJLoader, meshUrl)
  }

  // Deep clone + center geometry + compute normals
  const clonedModel = useMemo(() => {
    // Dispose le clone précédent (géométries + matériaux + textures)
    if (prevModelRef.current) {
      disposeObject(prevModelRef.current)
      prevModelRef.current = null
    }
    // Dispose les textures chargées par loadTextures() (onBeforeCompile ne les expose pas)
    prevTexturesRef.current.forEach(t => t.dispose())
    prevTexturesRef.current = []

    const clone = model.clone(true)
    const ox = boundingBox?.center ? -boundingBox.center[0] : 0
    const oy = boundingBox?.center ? -boundingBox.center[1] : 0
    const oz = boundingBox?.center ? -boundingBox.center[2] : 0

    clone.traverse(child => {
      if (child.isMesh) {
        if (child.geometry) {
          const oldGeo = child.geometry
          child.geometry = oldGeo.clone()
          oldGeo.dispose() // Dispose la géométrie du clone(true), remplacée par la version translatée
          child.geometry.translate(ox, oy, oz)
          if (!child.geometry.attributes.normal) {
            child.geometry.computeVertexNormals()
          }
        }
        // Dispose le matériau du clone(true) avant remplacement
        const clonedMat = child.material

        if (materialPreset?.procedural) {
          const pc = materialPreset.procedural
          const diagonal = boundingBox?.diagonal || 1
          const textureScale = (pc.scale || 3.0) / diagonal
          const textures = loadTextures(pc)
          prevTexturesRef.current.push(textures.colorMap, textures.normalMap, textures.roughnessMap)
          const mat = new THREE.MeshStandardMaterial({
            roughness: 0.5,
            metalness: 0.0,
            side: THREE.DoubleSide
          })
          mat.onBeforeCompile = (shader) => {
            shader.uniforms.uColorMap = { value: textures.colorMap }
            shader.uniforms.uRoughnessMap = { value: textures.roughnessMap }
            shader.uniforms.uTextureScale = { value: textureScale }
            shader.uniforms.uBlendSharpness = { value: pc.blendSharpness || 2.0 }

            // Add varyings + uniforms to vertex shader
            shader.vertexShader = shader.vertexShader.replace(
              '#include <common>',
              `#include <common>
              varying vec3 vWorldPos;
              varying vec3 vWorldNorm;`
            )
            shader.vertexShader = shader.vertexShader.replace(
              '#include <worldpos_vertex>',
              `#include <worldpos_vertex>
              vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
              vWorldNorm = normalize((modelMatrix * vec4(normal, 0.0)).xyz);`
            )

            // Add tri-planar sampling to fragment shader
            shader.fragmentShader = shader.fragmentShader.replace(
              '#include <common>',
              `#include <common>
              uniform sampler2D uColorMap;
              uniform sampler2D uRoughnessMap;
              uniform float uTextureScale;
              uniform float uBlendSharpness;
              varying vec3 vWorldPos;
              varying vec3 vWorldNorm;

              vec3 triplanarBlend(vec3 normal) {
                vec3 blend = pow(abs(normal), vec3(uBlendSharpness));
                return blend / (blend.x + blend.y + blend.z);
              }
              vec4 triplanarSample(sampler2D tex, vec3 pos, vec3 blend) {
                return texture2D(tex, pos.yz) * blend.x
                     + texture2D(tex, pos.xz) * blend.y
                     + texture2D(tex, pos.xy) * blend.z;
              }`
            )

            // Replace diffuse color with tri-planar sampled color
            shader.fragmentShader = shader.fragmentShader.replace(
              '#include <map_fragment>',
              `vec3 tpPos = vWorldPos * uTextureScale;
              vec3 tpBlend = triplanarBlend(vWorldNorm);
              diffuseColor.rgb = triplanarSample(uColorMap, tpPos, tpBlend).rgb;`
            )

            // Replace roughness with tri-planar sampled roughness
            shader.fragmentShader = shader.fragmentShader.replace(
              '#include <roughnessmap_fragment>',
              `float roughnessFactor = triplanarSample(uRoughnessMap, tpPos, tpBlend).r;`
            )
          }
          child.material = mat
        } else if (materialPreset?.visual) {
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
              side: THREE.DoubleSide
            })
          }
        } else if (child.material) {
          child.material = clonedMat.clone()
        }
        // Dispose le matériau orphelin du clone(true) remplacé ci-dessus
        if (clonedMat && clonedMat !== child.material) {
          clonedMat.dispose()
        }
        child.castShadow = true
        child.receiveShadow = true
      }
    })
    prevModelRef.current = clone
    return clone
  }, [model, boundingBox, materialPreset])

  // Cleanup au démontage
  useEffect(() => {
    return () => {
      if (prevModelRef.current) {
        disposeObject(prevModelRef.current)
        prevModelRef.current = null
      }
      prevTexturesRef.current.forEach(t => t.dispose())
      prevTexturesRef.current = []
    }
  }, [])

  // Extract and subsample vertices for a simplified convex hull collider
  const hullPoints = useMemo(() => {
    const allPositions = []
    clonedModel.traverse(child => {
      if (child.isMesh && child.geometry?.attributes?.position) {
        const pos = child.geometry.attributes.position.array
        for (let i = 0; i < pos.length; i++) {
          allPositions.push(pos[i])
        }
      }
    })
    return subsampleVertices(allPositions, 256)
  }, [clonedModel])

  //const rbRef = useRef(null)

  // Compute a sensible base mass from bounding box diagonal
  // (auto-computed hull mass is ~0.001, far too small for visible effect)
  const baseMass = useMemo(() => {
    const d = boundingBox?.diagonal || 1
    return d * d * d  // volume-proportional: 1m mesh = 1kg, 2m mesh = 8kg
  }, [boundingBox])

  // Apply mass multiplier + restitution via direct Rapier API
  // density is a multiplier (0.1 = 10%, 10.0 = 1000% of base mass)
  useEffect(() => {
    const timer = setTimeout(() => {
      const rb = rbRef.current
      if (!rb || rb.numColliders() === 0) return

      const targetMass = baseMass * density
      rb.setAdditionalMass(targetMass, true)
      rb.setLinearDamping(damping)
      rb.setAngularDamping(damping)
      for (let i = 0; i < rb.numColliders(); i++) {
        rb.collider(i).setRestitution(restitution)
        rb.collider(i).setFriction(damping * 2.0)
      }
      rb.wakeUp()
    }, 100)
    return () => clearTimeout(timer)
  }, [density, restitution, damping, baseMass])

  return (
    <RigidBody
      ref={rbRef}
      type="dynamic"
      colliders={false}
      position={[0, dropHeight, 0]}
      linearDamping={damping}
      angularDamping={damping}
    >
      <ConvexHullCollider args={[hullPoints]} />
      <primitive object={clonedModel} />
    </RigidBody>
  )
}

/**
 * PhysicsPlayground - Physics scene with ground, mesh, and projectiles.
 */
function ShadowLight({ diagonal }) {
  const lightRef = useRef()

  useEffect(() => {
    const light = lightRef.current
    if (!light) return
    const cam = light.shadow.camera
    cam.left = -diagonal * 2
    cam.right = diagonal * 2
    cam.top = diagonal * 2
    cam.bottom = -diagonal * 2
    cam.near = diagonal * 0.1
    cam.far = diagonal * 10
    cam.updateProjectionMatrix()
    light.shadow.mapSize.width = 2048
    light.shadow.mapSize.height = 2048
    light.shadow.bias = 0
    light.shadow.normalBias = diagonal * 0.005
    light.shadow.needsUpdate = true
  }, [diagonal])

  return (
    <directionalLight
      ref={lightRef}
      position={[diagonal * 2, diagonal * 4, diagonal * 2]}
      intensity={2.0}
      castShadow
    />
  )
}

function PhysicsPlayground({ meshInfo, gravity, density, restitution, damping, projectiles, materialPreset }) {
  const bb = meshInfo.bounding_box
  const diagonal = bb?.diagonal || 2

  const groundSize = diagonal * 3
  const groundThickness = diagonal
  const dropHeight = diagonal * 1.5
  const sphereRadius = diagonal * 0.08
  // Sphere mass = same as mesh base mass for strong impact
  const baseMass = diagonal * diagonal * diagonal
  const sphereMass = baseMass

  return (
    <Physics gravity={[0, gravity, 0]}>
      {/* Lighting - positions scaled to mesh size for correct shadow resolution */}
      <ambientLight intensity={0.35} />
      <ShadowLight diagonal={diagonal} />
      <directionalLight position={[-diagonal * 2, diagonal * 2, -diagonal * 2]} intensity={0.3} />

      {/* Ground - thick slab like official demos (thin slabs cause instabilities) */}
      <RigidBody type="fixed" colliders="cuboid">
        <mesh position={[0, -groundThickness / 2, 0]} receiveShadow>
          <boxGeometry args={[groundSize, groundThickness, groundSize]} />
          <meshStandardMaterial color="#8a8a8a" />
        </mesh>
      </RigidBody>

      {/* Grid */}
      <gridHelper args={[groundSize, 20, '#444444', '#333333']} position={[0, 0.001, 0]} />

      {/* User's mesh */}
      <Suspense fallback={null}>
        <PhysicsMesh
          filename={meshInfo.displayFilename || meshInfo.filename}
          isGenerated={meshInfo.isGenerated || false}
          isSimplified={meshInfo.isSimplified || false}
          isRetopologized={meshInfo.isRetopologized || false}
          isSegmented={meshInfo.isSegmented || false}
          density={density}
          restitution={restitution}
          damping={damping}
          dropHeight={dropHeight}
          boundingBox={bb}
          materialPreset={materialPreset}
        />
      </Suspense>

      {/* Projectiles */}
      {projectiles.map(p => (
        <RigidBody
          key={p.id}
          type="dynamic"
          colliders={false}
          position={p.position}
          linearVelocity={p.velocity}
        >
          <BallCollider args={[sphereRadius]} mass={sphereMass} restitution={restitution} />
          <mesh>
            <sphereGeometry args={[sphereRadius, 16, 16]} />
            <meshStandardMaterial color="#ef4444" />
          </mesh>
        </RigidBody>
      ))}
    </Physics>
  )
}

export default PhysicsPlayground
