import { useEffect, useRef } from 'react'
import { GUI } from 'lil-gui'

/**
 * Hook to create and manage a lil-gui debug panel for shader uniforms
 *
 * @param {Object} shaderConfig - Shader configuration from shaders/materials/
 * @param {Object} shaderParams - Current runtime parameters
 * @param {Function} onParamChange - Callback when a parameter changes: (key, value) => void
 * @param {boolean} enabled - Whether debug mode is enabled
 */
export function useShaderDebugGUI(shaderConfig, shaderParams, onParamChange, enabled) {
  const guiRef = useRef(null)
  const controllersRef = useRef({})
  const isResettingRef = useRef(false)

  useEffect(() => {
    // Cleanup existing GUI if debug is disabled or no shader active
    if (!enabled || !shaderConfig) {
      if (guiRef.current) {
        guiRef.current.destroy()
        guiRef.current = null
        controllersRef.current = {}
      }
      return
    }

    // Only create GUI if it doesn't exist yet
    if (guiRef.current) {
      return
    }

    // Create GUI instance
    const gui = new GUI({
      title: `${shaderConfig.name} Debug`,
      width: 300
    })

    // Position in top-right corner
    gui.domElement.style.position = 'fixed'
    gui.domElement.style.top = '80px'
    gui.domElement.style.right = '20px'
    gui.domElement.style.zIndex = '1000'

    guiRef.current = gui

    console.log('[ShaderDebugGUI] Creating debug panel for:', shaderConfig.name)

    // Helper to convert array [r, g, b] (0-1) to hex string
    const toHex = (rgb) => {
      const r = Math.round(rgb[0] * 255).toString(16).padStart(2, '0')
      const g = Math.round(rgb[1] * 255).toString(16).padStart(2, '0')
      const b = Math.round(rgb[2] * 255).toString(16).padStart(2, '0')
      return `#${r}${g}${b}`
    }

    // Helper to convert hex string to array [r, g, b] (0-1)
    const fromHex = (hex) => {
      const r = parseInt(hex.slice(1, 3), 16) / 255
      const g = parseInt(hex.slice(3, 5), 16) / 255
      const b = parseInt(hex.slice(5, 7), 16) / 255
      return [r, g, b]
    }

    // Create controls dynamically from shader uniforms config
    Object.entries(shaderConfig.uniforms).forEach(([key, config]) => {
      const currentValue = shaderParams[key] !== undefined
        ? shaderParams[key]
        : config.value

      let controller

      switch (config.type) {
        case 'color': {
          // Color picker - convert [r,g,b] to hex
          const proxy = { [key]: toHex(currentValue) }
          controller = gui.addColor(proxy, key).name(config.label || key)
          controller.onChange((hexValue) => {
            onParamChange(key, fromHex(hexValue))
          })
          break
        }

        case 'float': {
          // Slider for float values
          const min = config.min !== undefined ? config.min : 0
          const max = config.max !== undefined ? config.max : 1
          const step = config.step !== undefined ? config.step : 0.01

          // Create a stable proxy object stored in controllersRef
          const proxy = { value: currentValue }
          controllersRef.current[key + '_proxy'] = proxy

          controller = gui.add(proxy, 'value', min, max, step).name(config.label || key)
          controller.onChange((value) => {
            onParamChange(key, value)
          })
          break
        }

        case 'int': {
          // Integer slider
          const min = config.min !== undefined ? config.min : 0
          const max = config.max !== undefined ? config.max : 10
          const step = config.step !== undefined ? config.step : 1

          // Create a stable proxy object stored in controllersRef
          const proxy = { value: currentValue }
          controllersRef.current[key + '_proxy'] = proxy

          controller = gui.add(proxy, 'value', min, max, step).name(config.label || key)
          controller.onChange((value) => {
            const roundedValue = Math.round(value)
            onParamChange(key, roundedValue)
          })
          break
        }

        case 'vec2': {
          // Folder for vec2 with X, Y controls
          const folder = gui.addFolder(config.label || key)
          const proxy = {
            x: currentValue[0],
            y: currentValue[1]
          }

          const xCtrl = folder.add(proxy, 'x', config.min || -10, config.max || 10, config.step || 0.01)
          const yCtrl = folder.add(proxy, 'y', config.min || -10, config.max || 10, config.step || 0.01)

          const updateVec2 = () => {
            onParamChange(key, [proxy.x, proxy.y])
          }

          xCtrl.onChange(updateVec2)
          yCtrl.onChange(updateVec2)
          break
        }

        case 'vec3': {
          // Folder for vec3 with X, Y, Z controls
          const folder = gui.addFolder(config.label || key)
          const proxy = {
            x: currentValue[0],
            y: currentValue[1],
            z: currentValue[2]
          }

          const xCtrl = folder.add(proxy, 'x', config.min || -10, config.max || 10, config.step || 0.01)
          const yCtrl = folder.add(proxy, 'y', config.min || -10, config.max || 10, config.step || 0.01)
          const zCtrl = folder.add(proxy, 'z', config.min || -10, config.max || 10, config.step || 0.01)

          const updateVec3 = () => {
            onParamChange(key, [proxy.x, proxy.y, proxy.z])
          }

          xCtrl.onChange(updateVec3)
          yCtrl.onChange(updateVec3)
          zCtrl.onChange(updateVec3)
          break
        }

        case 'bool': {
          // Checkbox for boolean
          const proxy = { [key]: currentValue }
          controller = gui.add(proxy, key).name(config.label || key)
          controller.onChange((value) => {
            onParamChange(key, value)
          })
          break
        }

        default:
          console.warn(`[ShaderDebugGUI] Unsupported uniform type: ${config.type}`)
      }

      if (controller) {
        controllersRef.current[key] = controller
      }
    })

    // Add Reset button at the bottom
    const actions = {
      reset: () => {
        console.log('[ShaderDebugGUI] Resetting to default values')

        // Update all controller values to defaults
        Object.entries(shaderConfig.uniforms).forEach(([key, config]) => {
          const defaultValue = config.value
          const controller = controllersRef.current[key]
          const proxy = controllersRef.current[key + '_proxy']

          if (controller && proxy) {
            // Update proxy value
            proxy.value = defaultValue
            // Update controller display
            controller.updateDisplay()
          }
        })

        // Notify parent to reset params
        onParamChange(null, 'RESET_ALL')
      }
    }
    gui.add(actions, 'reset').name('🔄 Reset to Defaults')

    // Cleanup on unmount
    return () => {
      console.log('[ShaderDebugGUI] Destroying debug panel')
      gui.destroy()
      guiRef.current = null
      controllersRef.current = {}
    }
  }, [enabled, shaderConfig?.id]) // Only recreate when enabled state or shader changes

  return guiRef
}

export default useShaderDebugGUI
