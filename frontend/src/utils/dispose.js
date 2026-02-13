/**
 * Disposal récursif pour libérer la VRAM (géométries, matériaux, textures).
 * Utiliser avant de remplacer un objet 3D ou au démontage d'un composant.
 */

function disposeMaterial(mat) {
  if (!mat) return
  // Libérer toutes les textures attachées au matériau (map, normalMap, etc.)
  for (const key in mat) {
    if (mat[key]?.isTexture) {
      mat[key].dispose()
    }
  }
  // Libérer les textures dans les uniforms (ShaderMaterial + onBeforeCompile)
  if (mat.uniforms) {
    for (const key in mat.uniforms) {
      if (mat.uniforms[key]?.value?.isTexture) {
        mat.uniforms[key].value.dispose()
      }
    }
  }
  mat.dispose()
}

export function disposeObject(obj) {
  if (!obj) return

  obj.traverse((child) => {
    if (child.geometry) {
      child.geometry.dispose()
    }

    if (child.material) {
      if (Array.isArray(child.material)) {
        child.material.forEach(disposeMaterial)
      } else {
        disposeMaterial(child.material)
      }
    }
  })
}
