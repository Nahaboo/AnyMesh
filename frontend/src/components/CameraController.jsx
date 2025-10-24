import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'

/**
 * Ajuste automatiquement la position de la caméra selon la bounding box du mesh
 */
function CameraController({ boundingBox }) {
  const { camera, controls } = useThree()

  useEffect(() => {
    if (!boundingBox || !boundingBox.diagonal) {
      return
    }

    // Calculer la distance optimale de la caméra
    // Formule : distance = diagonale * facteur
    // Le facteur dépend du FOV de la caméra (ici 50°)
    const fov = camera.fov || 50
    const fovRadians = (fov * Math.PI) / 180
    const distance = boundingBox.diagonal / (2 * Math.tan(fovRadians / 2))

    // Ajouter une marge de 20% pour avoir de l'espace autour du modèle
    // Facteur fixe car tous les meshes sont maintenant normalisés et centrés par le backend
    const cameraDistance = distance * 1.2

    // Position de la caméra (vue isométrique 3/4)
    const angle = Math.PI / 4 // 45 degrés
    const height = cameraDistance * 0.7
    const radius = Math.sqrt(cameraDistance ** 2 - height ** 2)

    const newPosition = [
      boundingBox.center[0] + radius * Math.cos(angle),
      boundingBox.center[1] + height,
      boundingBox.center[2] + radius * Math.sin(angle)
    ]

    // Appliquer la nouvelle position
    camera.position.set(...newPosition)

    // Pointer la caméra vers le centre du mesh
    camera.lookAt(
      boundingBox.center[0],
      boundingBox.center[1],
      boundingBox.center[2]
    )

    // Ajuster les limites des contrôles OrbitControls
    if (controls) {
      controls.target.set(
        boundingBox.center[0],
        boundingBox.center[1],
        boundingBox.center[2]
      )
      controls.minDistance = cameraDistance * 0.2
      controls.maxDistance = cameraDistance * 3
      controls.update()
    }

    console.log('📷 Camera adjusted:', {
      boundingBox: boundingBox,
      cameraDistance: cameraDistance.toFixed(2),
      position: newPosition.map(v => v.toFixed(2))
    })
  }, [boundingBox, camera, controls])

  return null // Ce composant ne rend rien, il ajuste juste la caméra
}

export default CameraController
