/**
 * Service API pour communiquer avec le backend FastAPI
 * Base URL configurable via VITE_API_BASE_URL
 */

import axios from 'axios'

// Q4: URL backend configurable via variable d'environnement
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Export pour utilisation dans d'autres fichiers
export { API_BASE_URL }

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
      flat_multiplier: params.flat_multiplier,
      is_generated: params.is_generated || false
    }
  } else {
    requestParams = {
      filename: params.filename,
      reduction_ratio: params.reduction_ratio,
      preserve_boundary: params.preserve_boundary,
      is_generated: params.is_generated || false
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
 * P3: Ajout d'un timeout pour eviter le polling infini
 * @param {string} taskId - ID de la tache
 * @param {function} onProgress - Callback appele a chaque update
 * @param {number} interval - Intervalle de polling en ms (default: 1000)
 * @param {number} maxAttempts - Nombre max de tentatives (default: 300 = 5 min)
 * @returns {Promise} Resultat final de la tache
 */
export const pollTaskStatus = async (taskId, onProgress, interval = 1000, maxAttempts = 300) => {
  return new Promise((resolve, reject) => {
    let attempts = 0
    let networkRetries = 0
    const maxNetworkRetries = 3

    const poll = async () => {
      attempts++

      // P3: Timeout apres maxAttempts
      if (attempts > maxAttempts) {
        reject(new Error(`Timeout: La tache ${taskId} a pris trop de temps (>${Math.round(maxAttempts * interval / 1000)}s)`))
        return
      }

      try {
        const task = await getTaskStatus(taskId)
        networkRetries = 0 // Reset sur succes

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
        // Retry sur erreur reseau (3 tentatives max)
        networkRetries++
        if (networkRetries < maxNetworkRetries) {
          console.warn(`[pollTaskStatus] Erreur reseau (tentative ${networkRetries}/${maxNetworkRetries}):`, error.message)
          setTimeout(poll, interval * 2) // Backoff x2
        } else {
          reject(error)
        }
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
 * GLB-First: Le format de sortie est toujours GLB (natif de l'API Stability)
 * @param {Object} params - Paramètres de génération
 * @param {string} params.sessionId - ID de session (images uploadées)
 * @param {string} params.resolution - Résolution: 'low', 'medium', 'high'
 * @param {string} params.remeshOption - Topologie: 'none', 'triangle', 'quad' (optionnel, défaut: 'quad')
 * @returns {Promise} task_id et infos
 */
export const generateMesh = async (params) => {
  const response = await api.post('/generate-mesh', {
    session_id: params.sessionId,
    resolution: params.resolution,
    remesh_option: params.remeshOption || 'quad',
    provider: params.provider || 'stability'
  })
  return response.data
}

/**
 * Lance une tache de generation d'image a partir d'un prompt textuel via Mamouth.ai
 * @param {Object} params - Parametres de generation
 * @param {string} params.prompt - Description textuelle de l'image
 * @param {string} params.resolution - 'low', 'medium', 'high'
 * @returns {Promise} task_id et status
 */
export const generateImageFromPrompt = async (params) => {
  const response = await api.post('/generate-image-from-prompt', {
    prompt: params.prompt,
    resolution: params.resolution || 'medium'
  })
  return response.data
}

/**
 * Lance une tache de generation de texture seamless via Mamouth.ai
 * @param {Object} params - Parametres de generation
 * @param {string} params.prompt - Description du materiau
 * @param {string} params.resolution - 'low', 'medium', 'high'
 * @returns {Promise} task_id et status
 */
export const generateTexture = async (params) => {
  const response = await api.post('/generate-texture', {
    prompt: params.prompt,
    resolution: params.resolution || 'medium'
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

// ===== GLB-First: API SAUVEGARDE À LA DEMANDE =====

/**
 * Sauvegarde un mesh avec un nom personnalisé
 * @param {string} sourceFilename - Nom du fichier source
 * @param {string} saveName - Nom de la sauvegarde (sans extension)
 * @returns {Promise} Informations de la sauvegarde
 */
export const saveMesh = async (sourceFilename, saveName) => {
  const response = await api.post('/save', {
    source_filename: sourceFilename,
    save_name: saveName
  })
  return response.data
}

/**
 * Liste tous les meshes sauvegardés
 * @returns {Promise} Liste des meshes sauvegardés
 */
export const listSavedMeshes = async () => {
  const response = await api.get('/saved')
  return response.data
}

/**
 * Supprime un mesh sauvegardé
 * @param {string} filename - Nom du fichier à supprimer
 * @returns {Promise} Confirmation de suppression
 */
export const deleteSavedMesh = async (filename) => {
  const response = await api.delete(`/saved/${filename}`)
  return response.data
}

/**
 * Obtient l'URL d'un mesh sauvegardé
 * @param {string} filename - Nom du fichier sauvegardé
 * @returns {string} URL du mesh sauvegardé
 */
export const getSavedMeshUrl = (filename) => {
  return `${API_BASE_URL}/mesh/saved/${filename}`
}

export default api
