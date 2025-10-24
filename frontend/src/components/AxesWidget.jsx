import { Canvas, useFrame } from '@react-three/fiber'
import { useRef } from 'react'

/**
 * AxesDisplay - 3D axes that follow the main camera rotation
 */
function AxesDisplay({ mainCameraQuaternion, size, thickness }) {
  const groupRef = useRef()

  useFrame(() => {
    if (groupRef.current && mainCameraQuaternion) {
      // Apply the main camera's rotation to this group
      groupRef.current.quaternion.copy(mainCameraQuaternion)
    }
  })

  const halfSize = size / 2

  return (
    <group ref={groupRef}>
      {/* X axis - Red */}
      <mesh position={[halfSize, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[thickness, thickness, size, 8]} />
        <meshStandardMaterial color="#ff0000" />
      </mesh>

      {/* Y axis - Green */}
      <mesh position={[0, halfSize, 0]}>
        <cylinderGeometry args={[thickness, thickness, size, 8]} />
        <meshStandardMaterial color="#00ff00" />
      </mesh>

      {/* Z axis - Blue */}
      <mesh position={[0, 0, halfSize]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[thickness, thickness, size, 8]} />
        <meshStandardMaterial color="#0000ff" />
      </mesh>
    </group>
  )
}

/**
 * AxesWidget - Small widget showing 3D orientation synchronized with main camera
 * This widget follows the rotation of the main 3D viewer
 * @param {number} size - Length of each axis (default: 10.0)
 * @param {number} thickness - Thickness/radius of the axis cylinders (default: 0.1)
 */
function AxesWidget({ mainCameraQuaternion, size = 2.2, thickness = 0.13 }) {
  return (
    <div style={{
      width: '80px',
      height: '80px',
      overflow: 'hidden'
    }}>
      <Canvas camera={{ position: [0, 0, 5], fov: 50 }} gl={{ alpha: true }}>
        <ambientLight intensity={0.8} />
        <directionalLight position={[5, 5, 5]} intensity={0.8} />

        <AxesDisplay mainCameraQuaternion={mainCameraQuaternion} size={size} thickness={thickness} />
      </Canvas>
    </div>
  )
}

export default AxesWidget
