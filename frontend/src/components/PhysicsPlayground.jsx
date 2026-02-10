import { useMemo, useRef, useEffect, Suspense } from 'react'
import { useLoader } from '@react-three/fiber'
import { Physics, RigidBody, BallCollider, ConvexHullCollider } from '@react-three/rapier'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader'
import * as THREE from 'three'
import { API_BASE_URL } from '../utils/api'
import vertexShader from '../shaders/materials/triplanar/vertex.glsl'
import fragmentShader from '../shaders/materials/triplanar/fragment.glsl'
import glassFragmentShader from '../shaders/materials/triplanar/glass.glsl'

const textureLoader = new THREE.TextureLoader()

function loadTextures(type) {
  const path = `/textures/${type}`
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
function PhysicsMesh({ filename, isGenerated, density, restitution, damping, dropHeight, boundingBox, materialPreset }) {
  const meshUrl = isGenerated
    ? `${API_BASE_URL}/mesh/generated/${filename}`
    : `${API_BASE_URL}/mesh/input/${filename}`

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
    const clone = model.clone()
    const ox = boundingBox?.center ? -boundingBox.center[0] : 0
    const oy = boundingBox?.center ? -boundingBox.center[1] : 0
    const oz = boundingBox?.center ? -boundingBox.center[2] : 0

    clone.traverse(child => {
      if (child.isMesh) {
        if (child.geometry) {
          child.geometry = child.geometry.clone()
          child.geometry.translate(ox, oy, oz)
          if (!child.geometry.attributes.normal) {
            child.geometry.computeVertexNormals()
          }
        }
        if (materialPreset?.procedural) {
          const pc = materialPreset.procedural
          const diagonal = boundingBox?.diagonal || 1
          const textureScale = (pc.scale || 3.0) / diagonal
          const textures = loadTextures(pc.type)
          child.material = new THREE.ShaderMaterial({
            uniforms: {
              uColorMap: { value: textures.colorMap },
              uNormalMap: { value: textures.normalMap },
              uRoughnessMap: { value: textures.roughnessMap },
              uTextureScale: { value: textureScale },
              uBlendSharpness: { value: pc.blendSharpness || 2.0 },
              uLightDir: { value: new THREE.Vector3(1, 1, 1).normalize() }
            },
            vertexShader,
            fragmentShader,
            side: THREE.DoubleSide,
            lights: false
          })
        } else if (materialPreset?.visual) {
          const v = materialPreset.visual
          if (v.transparent) {
            // Glass: custom shader for smooth rendering
            child.material = new THREE.ShaderMaterial({
              vertexShader,
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
          child.material = child.material.clone()
        }
      }
    })
    return clone
  }, [model, boundingBox, materialPreset])

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

  const rbRef = useRef(null)

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
function PhysicsPlayground({ meshInfo, gravity, density, restitution, damping, projectiles, materialPreset }) {
  const bb = meshInfo.bounding_box
  const diagonal = bb?.diagonal || 2

  const groundSize = diagonal * 3
  const groundThickness = diagonal
  const dropHeight = diagonal * 0.5
  const sphereRadius = diagonal * 0.08
  // Sphere mass = same as mesh base mass for strong impact
  const baseMass = diagonal * diagonal * diagonal
  const sphereMass = baseMass

  return (
    <Physics gravity={[0, gravity, 0]}>
      {/* Lighting */}
      <directionalLight position={[5, 10, 5]} intensity={0.8} />
      <directionalLight position={[-5, 5, -5]} intensity={0.3} />

      {/* Ground - thick slab like official demos (thin slabs cause instabilities) */}
      <RigidBody type="fixed" colliders="cuboid">
        <mesh position={[0, -groundThickness / 2, 0]}>
          <boxGeometry args={[groundSize, groundThickness, groundSize]} />
          <meshStandardMaterial color="#2a2a2a" />
        </mesh>
      </RigidBody>

      {/* Grid */}
      <gridHelper args={[groundSize, 20, '#444444', '#333333']} position={[0, 0.001, 0]} />

      {/* User's mesh */}
      <Suspense fallback={null}>
        <PhysicsMesh
          filename={meshInfo.displayFilename || meshInfo.filename}
          isGenerated={meshInfo.isGenerated || false}
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
