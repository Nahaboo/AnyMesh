import { useState, useRef, useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import * as THREE from 'three'

/**
 * Hook to perform raycasting from mouse to 3D mesh
 * Returns the world position where the mouse intersects the mesh
 *
 * @param {THREE.Object3D} mesh - The mesh to raycast against
 * @param {boolean} enabled - Whether raycasting is enabled
 * @param {number} throttleMs - Throttle interval in milliseconds (default 50ms)
 * @returns {[number, number, number] | null} World position [x, y, z] or null if no hit
 */
export function useMouseRaycast(mesh, enabled = true, throttleMs = 50) {
  const [worldPosition, setWorldPosition] = useState(null)
  const raycaster = useRef(new THREE.Raycaster())
  const lastUpdateTime = useRef(0)
  const { camera, pointer, gl } = useThree()

  useEffect(() => {
    if (!enabled || !mesh) {
      setWorldPosition(null)
      return
    }

    const handleMouseMove = () => {
      const now = Date.now()

      // Throttle raycasting to avoid performance issues
      if (now - lastUpdateTime.current < throttleMs) {
        return
      }

      lastUpdateTime.current = now

      // Update raycaster with current mouse position
      raycaster.current.setFromCamera(pointer, camera)

      // Perform raycasting
      const intersects = raycaster.current.intersectObject(mesh, true)

      if (intersects.length > 0) {
        const point = intersects[0].point
        setWorldPosition([point.x, point.y, point.z])
      } else {
        // Mouse not hovering the mesh
        setWorldPosition(null)
      }
    }

    // Listen to mouse move events on the canvas
    const canvas = gl.domElement
    canvas.addEventListener('mousemove', handleMouseMove)

    return () => {
      canvas.removeEventListener('mousemove', handleMouseMove)
    }
  }, [enabled, mesh, camera, pointer, gl, throttleMs])

  return worldPosition
}

export default useMouseRaycast
