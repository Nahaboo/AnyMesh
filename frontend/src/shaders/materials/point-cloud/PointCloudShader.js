import vertexShader from './vertex.glsl'
import fragmentShader from './fragment.glsl'

export const PointCloudShader = {
  id: 'point-cloud',
  name: 'Point Cloud Animated',
  type: 'material',
  description: 'Animated point cloud with organic movement',

  uniforms: {
    // Animation
    uTime: {
      value: 0.0,
      type: 'float',
      animated: true,
      hidden: true
    },

    // Point appearance
    uPointSize: {
      value: 3.0,
      type: 'float',
      min: 1.0,
      max: 20.0,
      step: 0.5,
      label: 'Point Size',
      description: 'Size of each point in pixels'
    },

    uColor: {
      value: [0.3, 0.6, 0.9],
      type: 'color',
      label: 'Point Color',
      description: 'Base color of points'
    },

    // Animation parameters
    uAmplitude: {
      value: 0.02,
      type: 'float',
      min: 0.0,
      max: 0.1,
      step: 0.001,
      label: 'Amplitude',
      description: 'Movement intensity'
    },

    uSpeed: {
      value: 0.5,
      type: 'float',
      min: 0.0,
      max: 2.0,
      step: 0.1,
      label: 'Speed',
      description: 'Animation speed'
    },

    uFrequency: {
      value: 2.0,
      type: 'float',
      min: 0.1,
      max: 10.0,
      step: 0.1,
      label: 'Frequency',
      description: 'Noise frequency'
    },

    // Visual options
    uDepthFade: {
      value: true,
      type: 'bool',
      label: 'Depth Fade',
      description: 'Fade points based on depth'
    },

    // Auto-calculated (hidden)
    uMeshScale: {
      value: 1.0,
      type: 'float',
      hidden: true
    }
  },

  vertexShader,
  fragmentShader
}

export default PointCloudShader
