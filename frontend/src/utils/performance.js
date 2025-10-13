/**
 * Utilitaire pour mesurer les performances de chargement
 */

class PerformanceTracker {
  constructor() {
    this.measurements = new Map()
  }

  /**
   * Démarre un timer
   * @param {string} label - Nom de la mesure
   */
  start(label) {
    this.measurements.set(label, {
      start: performance.now(),
      end: null,
      duration: null
    })
    console.log(`🔵 [PERF] ${label} - START`)
  }

  /**
   * Arrête un timer et calcule la durée
   * @param {string} label - Nom de la mesure
   * @returns {number} Durée en millisecondes
   */
  end(label) {
    const measurement = this.measurements.get(label)
    if (!measurement) {
      console.warn(`⚠️ [PERF] ${label} - Timer not found`)
      return 0
    }

    measurement.end = performance.now()
    measurement.duration = measurement.end - measurement.start

    const duration = measurement.duration
    const color = duration < 100 ? '🟢' : duration < 1000 ? '🟡' : '🔴'

    console.log(`${color} [PERF] ${label} - END: ${duration.toFixed(2)}ms`)

    return duration
  }

  /**
   * Mesure une fonction asynchrone
   * @param {string} label - Nom de la mesure
   * @param {Function} fn - Fonction à mesurer
   * @returns {Promise} Résultat de la fonction
   */
  async measure(label, fn) {
    this.start(label)
    try {
      const result = await fn()
      this.end(label)
      return result
    } catch (error) {
      console.error(`❌ [PERF] ${label} - ERROR:`, error)
      throw error
    }
  }

  /**
   * Affiche un résumé de toutes les mesures frontend uniquement
   */
  summary() {
    console.log('\n📊 [FRONTEND PERF] Performance Summary:')
    console.log('=' .repeat(60))

    let total = 0
    this.measurements.forEach((measurement, label) => {
      if (measurement.duration !== null) {
        total += measurement.duration
        console.log(`  ${label.padEnd(40)} ${measurement.duration.toFixed(2).padStart(10)}ms`)
      }
    })

    console.log('=' .repeat(60))
    console.log(`  TOTAL${' '.repeat(35)} ${total.toFixed(2).padStart(10)}ms`)
    console.log('\n')
  }

  /**
   * Réinitialise toutes les mesures
   */
  reset() {
    this.measurements.clear()
  }
}

// Instance globale
export const perf = new PerformanceTracker()

// Export pour utilisation dans les composants
export default perf
