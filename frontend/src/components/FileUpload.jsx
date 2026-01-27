import { useState } from 'react'
import { uploadMesh } from '../utils/api'


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

      // GLB-First: Appel API avec conversion automatique vers GLB
      const response = await uploadMesh(file)

      clearInterval(progressInterval)
      setUploadProgress(100)

      // Success
      console.log('[FileUpload] Upload GLB-First reussi:', response)

      if (onUploadSuccess) {
        // GLB-First: mesh_info contient les données complètes
        const meshInfo = response.mesh_info
        // Ajouter uploadId pour forcer le rechargement du viewer
        meshInfo.uploadId = Date.now()
        onUploadSuccess(meshInfo)
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
    <div style={{ width: '100%' }}>
      {/* Zone de drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          position: 'relative',
          border: `2px dashed ${isDragging ? 'var(--v2-accent-primary)' : 'var(--v2-border-primary)'}`,
          background: isDragging ? 'var(--v2-info-bg)' : 'var(--v2-bg-secondary)',
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-xl)',
          textAlign: 'center',
          transition: 'all 200ms ease-in-out',
          opacity: isUploading ? 0.5 : 1,
          cursor: isUploading ? 'not-allowed' : 'pointer'
        }}
      >
        <input
          type="file"
          onChange={handleFileInput}
          accept={SUPPORTED_FORMATS.join(',')}
          style={{
            position: 'absolute',
            inset: '0',
            width: '100%',
            height: '100%',
            opacity: 0,
            cursor: isUploading ? 'not-allowed' : 'pointer'
          }}
          disabled={isUploading}
        />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
          {/* Icone */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <svg
              style={{ width: '64px', height: '64px', color: 'var(--v2-text-tertiary)' }}
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
            <p style={{
              fontSize: '18px',
              fontWeight: '500',
              color: 'var(--v2-text-primary)',
              margin: 0
            }}>
              {isUploading ? 'Upload en cours...' : 'Glissez un fichier 3D ici'}
            </p>
            <p style={{
              fontSize: '14px',
              color: 'var(--v2-text-secondary)',
              marginTop: 'var(--v2-spacing-xs)',
              marginBottom: 0
            }}>
              ou cliquez pour parcourir
            </p>
          </div>

          {/* Barre de progression */}
          {isUploading && (
            <div style={{ maxWidth: '300px', margin: '0 auto' }}>
              <div style={{
                width: '100%',
                background: 'var(--v2-bg-tertiary)',
                borderRadius: 'var(--v2-radius-full)',
                height: '8px',
                overflow: 'hidden'
              }}>
                <div style={{
                  background: 'var(--v2-accent-primary)',
                  height: '8px',
                  borderRadius: 'var(--v2-radius-full)',
                  width: `${uploadProgress}%`,
                  transition: 'width 300ms ease-in-out'
                }} />
              </div>
              <p style={{
                fontSize: '12px',
                color: 'var(--v2-text-muted)',
                marginTop: 'var(--v2-spacing-xs)',
                marginBottom: 0
              }}>
                {uploadProgress}%
              </p>
            </div>
          )}

          {/* Formats supportes */}
          {!isUploading && (
            <div style={{
              fontSize: '12px',
              color: 'var(--v2-text-muted)'
            }}>
              Formats supportes: {SUPPORTED_FORMATS.join(', ')}
            </div>
          )}
        </div>
      </div>

      {/* Message d'erreur */}
      {error && (
        <div style={{
          marginTop: 'var(--v2-spacing-md)',
          padding: 'var(--v2-spacing-md)',
          background: 'var(--v2-error-bg)',
          border: '1px solid var(--v2-error-border)',
          borderRadius: 'var(--v2-radius-lg)'
        }}>
          <p style={{
            fontSize: '14px',
            color: 'var(--v2-error-text)',
            margin: 0
          }}>
            {error}
          </p>
        </div>
      )}
    </div>
  )
}

export default FileUpload
