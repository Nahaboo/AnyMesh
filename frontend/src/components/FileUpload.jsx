import { useState } from 'react'
import { uploadMesh } from '../utils/api'

/**
 * Affiche les timings backend dans la console
 */
function displayBackendTimings(timings) {
  const getColor = (ms) => ms < 100 ? '🟢' : ms < 1000 ? '🟡' : '🔴'
  const formatLine = (label, value) =>
    `${getColor(value)} ${label.padEnd(15)} ${value.toFixed(2).padStart(10)}ms`

  console.log('\n📊 [BACKEND PERF] Upload & Analysis completed:')
  console.log('='.repeat(60))

  if (timings.file_save_ms != null) {
    console.log(formatLine('FILE_SAVE:', timings.file_save_ms))
  }

  // Support Open3D et Trimesh
  const meshLoadMs = timings.trimesh_load_ms || timings.open3d_load_ms
  if (meshLoadMs != null) {
    const label = timings.trimesh_load_ms ? 'TRIMESH_LOAD:' : 'OPEN3D_LOAD:'
    console.log(formatLine(label, meshLoadMs))
  }

  if (timings.analysis_ms != null) {
    console.log(formatLine('ANALYSIS:', timings.analysis_ms))
  }

  if (timings.total_ms != null) {
    console.log('='.repeat(60))
    console.log(formatLine('BACKEND TOTAL:', timings.total_ms))
  }

  console.log('\n')
}

function FileUpload({ onUploadSuccess }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)

  // Formats supportes (memes que le backend)
  const SUPPORTED_FORMATS = ['.obj', '.stl', '.ply', '.off', '.gltf', '.glb']

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFile(files[0])
    }
  }

  const handleFileInput = (e) => {
    const files = e.target.files
    if (files.length > 0) {
      handleFile(files[0])
    }
  }

  const handleFile = async (file) => {
    // Reset error
    setError(null)
    setUploadProgress(0)

    // Verifier l'extension
    const fileExt = '.' + file.name.split('.').pop().toLowerCase()
    if (!SUPPORTED_FORMATS.includes(fileExt)) {
      setError(`Format non supporte. Formats acceptes: ${SUPPORTED_FORMATS.join(', ')}`)
      return
    }

    // Upload vers le backend
    setIsUploading(true)
    setUploadProgress(10)

    try {
      // Simuler la progression
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)

      // Appel API
      const response = await uploadMesh(file)

      clearInterval(progressInterval)
      setUploadProgress(100)

      // Success
      console.log('Upload reussi:', response)

      // Afficher les traces backend immédiatement après l'upload
      if (response.backend_timings) {
        displayBackendTimings(response.backend_timings)
      }

      if (onUploadSuccess) {
        // Passer uniquement mesh_info (pas de backend_timings pour garder la séparation)
        onUploadSuccess(response.mesh_info)
      }

      // Reset apres 1 seconde
      setTimeout(() => {
        setIsUploading(false)
        setUploadProgress(0)
      }, 1000)

    } catch (err) {
      console.error('Erreur upload:', err)
      setError(err.response?.data?.detail || 'Erreur lors de l\'upload du fichier')
      setIsUploading(false)
      setUploadProgress(0)
    }
  }

  return (
    <div className="w-full">
      {/* Zone de drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-12 text-center transition-all
          ${isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400 bg-white'
          }
          ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <input
          type="file"
          onChange={handleFileInput}
          accept={SUPPORTED_FORMATS.join(',')}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />

        <div className="space-y-4">
          {/* Icone */}
          <div className="flex justify-center">
            <svg
              className="w-16 h-16 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>

          {/* Texte */}
          <div>
            <p className="text-lg font-medium text-gray-700">
              {isUploading ? 'Upload en cours...' : 'Glissez un fichier 3D ici'}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              ou cliquez pour parcourir
            </p>
          </div>

          {/* Barre de progression */}
          {isUploading && (
            <div className="max-w-xs mx-auto">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-2">{uploadProgress}%</p>
            </div>
          )}

          {/* Formats supportes */}
          {!isUploading && (
            <div className="text-xs text-gray-400">
              Formats supportes: {SUPPORTED_FORMATS.join(', ')}
            </div>
          )}
        </div>
      </div>

      {/* Message d'erreur */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
  )
}

export default FileUpload
