import vertexShaderRaw from './vertex.glsl'
import fragmentShader from './fragment.glsl'
import simplexNoise3D from '../common/noise.glsl'

// Inject noise function at the beginning of vertex shader
const vertexShader = simplexNoise3D + '\n' + vertexShaderRaw

export const OrganicSolidShader = {
  id: 'organic-solid',
  name: 'Organic Solid Shading',
  type: 'material',
  description: 'Organic movement with Perlin noise and mouse interaction - smooth solid shading',

  uniforms: {
    // Animation uniforms
    uTime: {
      value: 0.0,
      type: 'float',
      animated: true, // Special flag indicating this should be updated every frame
      hidden: true // Don't show in debug UI
    },

    // Movement parameters
    uAmplitude: {
      value: 0.01,
      type: 'float',
      min: 0.0,
      max: 0.05,
      step: 0.001,
      label: 'Amplitude',
      description: 'Intensity of the organic movement'
    },

    uSpeed: {
      value: 0.2,
      type: 'float',
      min: 0.0,
      max: 0.5,
      step: 0.01,
      label: 'Vitesse',
      description: 'Speed of the animation'
    },

    uMeshScale: {
      value: 1.0,
      type: 'float',
      hidden: true // Automatically calculated from bounding box
    },

    uFrequency: {
      value: 5.0,
      type: 'float',
      min: 0.1,
      max: 10.0,
      step: 0.1,
      label: 'Fréquence',
      description: 'Frequency of the noise pattern'
    },

    // Mouse interaction
    uMousePosition: {
      value: [0.0, 0.0, 0.0],
      type: 'vec3',
      hidden: true // Updated automatically by raycasting
    },

    uMouseInfluence: {
      value: 0.02,
      type: 'float',
      min: 0.0,
      max: 0.1,
      step: 0.001,
      label: 'Force Souris',
      description: 'Strength of mouse attraction (scaled by mesh size)'
    },

    uMouseRadius: {
      value: 0.15,
      type: 'float',
      min: 0.05,
      max: 0.5,
      step: 0.01,
      label: 'Rayon Souris',
      description: 'Radius of mouse influence (scaled by mesh size)'
    },

    // Visual parameters
    uColor: {
      value: [0.2, 0.6, 0.9],
      type: 'color',
      label: 'Couleur',
      description: 'Base color of the mesh'
    },

    uMouseHighlightColor: {
      value: [1.0, 0.3, 0.5],
      type: 'color',
      label: 'Couleur Souris',
      description: 'Highlight color when mouse interacts'
    },

    uLightDirection: {
      value: [1.0, 1.0, 1.0],
      type: 'vec3',
      min: -1.0,
      max: 1.0,
      step: 0.1,
      label: 'Direction Lumière',
      description: 'Direction of the main light'
    }
  },

  vertexShader,
  fragmentShader
}

export default OrganicSolidShader
