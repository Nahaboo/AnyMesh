// Material Shaders - Central Export
// All custom material shaders available in the application

import ToonShader from './toon/ToonShader'
import OrganicSolidShader from './organic-solid/OrganicSolidShader'

// Export all material shaders
export const materialShaders = {
  toon: ToonShader,
  'organic-solid': OrganicSolidShader
}

// Helper function to get shader by ID
export const getMaterialShader = (id) => {
  return materialShaders[id] || null
}

// Get list of all available shaders
export const getAllMaterialShaders = () => {
  return Object.values(materialShaders)
}

export default materialShaders
