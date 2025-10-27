// Toon Shader Configuration
// Cel-shading effect with quantized lighting levels

import vertexShader from './vertex.glsl'
import fragmentShader from './fragment.glsl'

export const ToonShader = {
  id: 'toon',
  name: 'Toon Shading',
  type: 'material',
  description: 'Cel-shading effect with cartoon-like appearance',

  // Shader uniforms with default values and UI configuration
  uniforms: {
    uColor: {
      value: [0.7, 0.8, 1.0], // Light blue
      type: 'color',
      label: 'Base Color',
      description: 'Main color of the mesh'
    },
    uLevels: {
      value: 4,
      type: 'int',
      min: 2,
      max: 10,
      step: 1,
      label: 'Shade Levels',
      description: 'Number of discrete lighting levels (more = smoother)'
    },
    uOutlineThickness: {
      value: 0.4,
      type: 'float',
      min: 0.0,
      max: 1.0,
      step: 0.01,
      label: 'Outline Thickness',
      description: 'Width of the outline around the mesh'
    },
    uLightDirection: {
      value: [1.0, 1.0, 1.0], // Top-right light
      type: 'vec3',
      label: 'Light Direction',
      description: 'Direction of the main light source'
    }
  },

  // GLSL shader code
  vertexShader,
  fragmentShader
}

export default ToonShader
