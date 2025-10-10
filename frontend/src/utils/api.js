/**
 * Service API pour communiquer avec le backend FastAPI
 * Base URL: http://localhost:8000
 */

import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

// Configuration axios avec base URL
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * API Health Check
 */
export const checkHealth = async () => {
  const response = await api.get('/health')
  return response.data
}

/**
 * Liste tous les maillages disponibles
 */
export const listMeshes = async () => {
  const response = await api.get('/meshes')
  return response.data
}

/**
 * Upload un fichier de maillage 3D
 * @param {File} file - Le fichier a uploader
 * @returns {Promise} Les informations du maillage uploade
 */
export const uploadMesh = async (file) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Lance une tache de simplification
 * @param {Object} params - Parametres de simplification
 * @param {string} params.filename - Nom du fichier a simplifier
 * @param {number} params.reduction_ratio - Ratio de reduction (0.0 - 1.0)
 * @param {number} params.target_triangles - Nombre cible de triangles (optionnel)
 * @param {boolean} params.preserve_boundary - Preserver les bords (default: true)
 * @returns {Promise} task_id et infos
 */
export const simplifyMesh = async (params) => {
  const response = await api.post('/simplify', params)
  return response.data
}

/**
 * Recupere le statut d'une tache
 * @param {string} taskId - ID de la tache
 * @returns {Promise} Informations de la tache
 */
export const getTaskStatus = async (taskId) => {
  const response = await api.get(`/tasks/${taskId}`)
  return response.data
}

/**
 * Liste toutes les taches
 * @returns {Promise} Liste des taches
 */
export const listTasks = async () => {
  const response = await api.get('/tasks')
  return response.data
}

/**
 * Genere l'URL de telechargement pour un fichier
 * @param {string} filename - Nom du fichier
 * @returns {string} URL de telechargement
 */
export const getDownloadUrl = (filename) => {
  return `${API_BASE_URL}/download/${filename}`
}

/**
 * Polling du statut d'une tache jusqu'a completion
 * @param {string} taskId - ID de la tache
 * @param {function} onProgress - Callback appele a chaque update
 * @param {number} interval - Intervalle de polling en ms (default: 1000)
 * @returns {Promise} Resultat final de la tache
 */
export const pollTaskStatus = async (taskId, onProgress, interval = 1000) => {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const task = await getTaskStatus(taskId)

        // Callback de progression
        if (onProgress) {
          onProgress(task)
        }

        // Verifier le statut
        if (task.status === 'completed') {
          resolve(task)
        } else if (task.status === 'failed') {
          reject(new Error(task.error || 'Task failed'))
        } else {
          // Continuer le polling
          setTimeout(poll, interval)
        }
      } catch (error) {
        reject(error)
      }
    }

    // Demarrer le polling
    poll()
  })
}

export default api
