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
 * Upload rapide d'un fichier de maillage 3D (pour visualisation immédiate)
 * @param {File} file - Le fichier a uploader
 * @returns {Promise} Les informations minimales du maillage (sans analyse complète)
 */
export const uploadMeshFast = async (file) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload-fast', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Upload un fichier de maillage 3D avec analyse complète
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
 * Analyse détaillée d'un fichier déjà uploadé
 * @param {string} filename - Nom du fichier à analyser
 * @returns {Promise} Les statistiques complètes du maillage
 */
export const analyzeMesh = async (filename) => {
  const response = await api.get(`/analyze/${filename}`)
  return response.data
}

/**
 * Lance une tache de simplification
 * @param {Object} params - Parametres de simplification
 * @param {string} params.mode - Mode: 'standard' ou 'adaptive'
 * @param {string} params.filename - Nom du fichier a simplifier
 * MODE STANDARD:
 * @param {number} params.reduction_ratio - Ratio de reduction (0.0 - 1.0)
 * @param {number} params.target_triangles - Nombre cible de triangles (optionnel)
 * @param {boolean} params.preserve_boundary - Preserver les bords (default: true)
 * MODE ADAPTATIF:
 * @param {number} params.target_ratio - Ratio de reduction de base (0.0 - 1.0)
 * @param {number} params.flat_multiplier - Multiplicateur pour zones plates (1.0 - 3.0)
 * @returns {Promise} task_id et infos
 */
export const simplifyMesh = async (params) => {
  // Choisir l'endpoint en fonction du mode
  const endpoint = params.mode === 'adaptive' ? '/simplify-adaptive' : '/simplify'

  // Préparer les paramètres selon le mode
  let requestParams
  if (params.mode === 'adaptive') {
    requestParams = {
      filename: params.filename,
      target_ratio: params.target_ratio,
      flat_multiplier: params.flat_multiplier
    }
  } else {
    requestParams = {
      filename: params.filename,
      reduction_ratio: params.reduction_ratio,
      preserve_boundary: params.preserve_boundary
    }
  }

  const response = await api.post(endpoint, requestParams)
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

// ===== API GÉNÉRATION DE MAILLAGES À PARTIR D'IMAGES =====

/**
 * Upload multiple d'images pour génération de maillage 3D
 * @param {File[]} files - Les fichiers images à uploader
 * @returns {Promise} session_id et informations des images uploadées
 */
export const uploadImages = async (files) => {
  const formData = new FormData()

  // Ajouter chaque image au FormData
  files.forEach((file) => {
    formData.append('files', file)
  })

  const response = await api.post('/upload-images', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Lance une tâche de génération de maillage à partir d'images
 * @param {Object} params - Paramètres de génération
 * @param {string} params.sessionId - ID de session (images uploadées)
 * @param {string} params.resolution - Résolution: 'low', 'medium', 'high'
 * @param {string} params.outputFormat - Format de sortie: 'obj', 'stl', 'ply'
 * @returns {Promise} task_id et infos
 */
export const generateMesh = async (params) => {
  const response = await api.post('/generate-mesh', {
    session_id: params.sessionId,
    resolution: params.resolution,
    output_format: params.outputFormat
  })
  return response.data
}

/**
 * Liste les images d'une session
 * @param {string} sessionId - ID de la session
 * @returns {Promise} Liste des images de la session
 */
export const listSessionImages = async (sessionId) => {
  const response = await api.get(`/sessions/${sessionId}/images`)
  return response.data
}

/**
 * Génère l'URL pour accéder à un maillage généré
 * @param {string} filename - Nom du fichier généré
 * @returns {string} URL du maillage généré
 */
export const getGeneratedMeshUrl = (filename) => {
  return `${API_BASE_URL}/mesh/generated/${filename}`
}

/**
 * Lance une tâche de segmentation de maillage
 * @param {Object} params - Paramètres de segmentation
 * @param {string} params.filename - Nom du fichier à segmenter
 * @param {string} params.method - Méthode: 'connectivity', 'sharp_edges', 'curvature', 'planes'
 * @param {number} [params.angle_threshold] - Pour sharp_edges (10-90°)
 * @param {number} [params.num_clusters] - Pour curvature (2-10)
 * @param {number} [params.num_planes] - Pour planes (1-6)
 * @returns {Promise} task_id et infos
 */
export const segmentMesh = async (params) => {
  const response = await api.post('/segment', params)
  return response.data
}

/**
 * Génère l'URL pour accéder à un maillage segmenté
 * @param {string} filename - Nom du fichier segmenté
 * @returns {string} URL du maillage segmenté
 */
export const getSegmentedMeshUrl = (filename) => {
  return `${API_BASE_URL}/mesh/segmented/${filename}`
}

/**
 * Lance une tâche de retopologie de maillage
 * @param {Object} params - Paramètres de retopologie
 * @param {string} params.filename - Nom du fichier à retopologiser
 * @param {number} params.target_face_count - Nombre de faces cibles (1000-50000)
 * @param {boolean} params.deterministic - Mode déterministe (default: true)
 * @param {boolean} params.preserve_boundaries - Préserver les bordures (default: true)
 * @returns {Promise} task_id et infos
 */
export const retopologizeMesh = async (params) => {
  const response = await api.post('/retopologize', params)
  return response.data
}

/**
 * Obtient l'URL d'un maillage retopologisé
 * @param {string} filename - Nom du fichier retopologisé
 * @returns {string} URL du maillage retopologisé
 */
export const getRetopologyMeshUrl = (filename) => {
  return `${API_BASE_URL}/mesh/retopo/${filename}`
}

export default api
