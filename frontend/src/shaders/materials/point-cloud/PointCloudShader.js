import vertexShaderRaw from './vertex.glsl'
import fragmentShader from './fragment.glsl'
import simplexNoise3D from '../common/noise.glsl'

// Inject noise function at the beginning of vertex shader
const vertexShader = simplexNoise3D + '\n' + vertexShaderRaw

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

    // Static layer
    uSizeStatic: {
      value: 2.1,
      type: 'float',
      min: 0.0,
      max: 15.0,
      step: 0.1,
      label: 'Static Size',
      description: 'Size of static points'
    },

    uColorStatic: {
      value: [0.3, 0.6, 0.9],
      type: 'color',
      label: 'Static Color',
      description: 'Color of static layer'
    },

    // Dynamic layer
    uSizeDynamic: {
      value: 5.0,
      type: 'float',
      min: 1.0,
      max: 15.0,
      step: 0.1,
      label: 'Dynamic Size',
      description: 'Size of animated points'
    },

    uColorDynamic: {
      value: [0.3, 0.6, 0.9],
      type: 'color',
      label: 'Dynamic Color',
      description: 'Color of dynamic layer'
    },

    // Animation parameters
    uAmplitude: {
      value: 0.02,
      type: 'float',
      min: 0.0,
      max: 0.1,
      step: 0.0001,
      label: 'Wave Amplitude',
      description: 'Height of waves'
    },

    uFrequency: {
      value: 21.0,
      type: 'float',
      min: 1.0,
      max: 40.0,
      step: 0.5,
      label: 'Wave Frequency',
      description: 'Frequency of waves'
    },

    uSpeed: {
      value: 1.30,
      type: 'float',
      min: 0.0,
      max: 4.0,
      step: 0.05,
      label: 'Animation Speed',
      description: 'Speed of animation'
    },

    uMotionMode: {
      value: 3,
      type: 'int',
      min: 0,
      max: 4,
      step: 1,
      label: 'Motion Mode',
      description: '0=Waves, 1=Pulse, 2=Turbulence, 3=Flow, 4=Breathe'
    },

    uDepthOffset: {
      value: 0.0025,
      type: 'float',
      min: 0.0,
      max: 0.02,
      step: 0.0001,
      label: 'Depth Offset',
      description: 'Offset along normals for depth effect'
    },

    // Performance options
    uPointDensity: {
      value: 1.0,
      type: 'float',
      min: 0.1,
      max: 1.0,
      step: 0.05,
      label: 'Point Density',
      description: '1.0=100%, Auto: 50% for >150k vertices (better performance)'
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
    },

    uTotalVertices: {
      value: 1.0,
      type: 'float',
      hidden: true
    },

    uIsStatic: {
      value: 0.0,
      type: 'float',
      hidden: true
    }
  },

  vertexShader,
  fragmentShader
}

export default PointCloudShader
