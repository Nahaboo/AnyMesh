import { useState } from 'react'
import { uploadImages } from '../utils/api'

function ImageUpload({ onUploadSuccess }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedImages, setSelectedImages] = useState([])
  const [previewUrls, setPreviewUrls] = useState([])

  // Formats supportés (images uniquement)
  const SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png']
  const MAX_IMAGE_SIZE = 20 * 1024 * 1024 // 20 MB par image (resize cote backend)

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

    const files = Array.from(e.dataTransfer.files)
    handleFiles(files)
  }

  const handleFileInput = (e) => {
    const files = Array.from(e.target.files)
    handleFiles(files)
  }

  const handleFiles = (files) => {
    // Reset error
    setError(null)

    // Filtrer et valider les fichiers
    const validImages = []
    const errors = []

    files.forEach(file => {
      const fileExt = '.' + file.name.split('.').pop().toLowerCase()

      if (!SUPPORTED_FORMATS.includes(fileExt)) {
        errors.push(`${file.name}: format non supporté`)
        return
      }

      if (file.size > MAX_IMAGE_SIZE) {
        errors.push(`${file.name}: taille trop grande (max 20 MB)`)
        return
      }

      validImages.push(file)
    })

    if (errors.length > 0) {
      setError(errors.join(', '))
      if (validImages.length === 0) return
    }

    // Créer les previews
    const newPreviewUrls = validImages.map(file => URL.createObjectURL(file))

    setSelectedImages(prev => [...prev, ...validImages])
    setPreviewUrls(prev => [...prev, ...newPreviewUrls])
  }

  const removeImage = (index) => {
    // Libérer l'URL de preview
    URL.revokeObjectURL(previewUrls[index])

    setSelectedImages(prev => prev.filter((_, i) => i !== index))
    setPreviewUrls(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (selectedImages.length === 0) {
      setError('Veuillez sélectionner au moins une image')
      return
    }

    setError(null)
    setIsUploading(true)

    try {
      console.log('🔵 [ImageUpload] Uploading', selectedImages.length, 'images')

      const response = await uploadImages(selectedImages)

      console.log('🟢 [ImageUpload] Upload successful:', response)

      if (onUploadSuccess) {
        onUploadSuccess({
          sessionId: response.session_id,
          images: response.images,
          imagesCount: response.images_count
        })
      }

      // Reset après succès
      setSelectedImages([])
      previewUrls.forEach(url => URL.revokeObjectURL(url))
      setPreviewUrls([])
      setIsUploading(false)

    } catch (err) {
      console.error('Erreur upload images:', err)
      setError(err.response?.data?.detail || 'Erreur lors de l\'upload des images')
      setIsUploading(false)
    }
  }

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
      {/* Zone de drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          position: 'relative',
          border: `2px dashed ${isDragging ? 'var(--v2-accent-primary)' : 'var(--v2-border-primary)'}`,
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-xl)',
          textAlign: 'center',
          transition: 'all var(--v2-transition-base)',
          background: isDragging ? 'var(--v2-info-bg)' : 'var(--v2-bg-secondary)',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          opacity: isUploading ? 0.5 : 1
        }}
      >
        <input
          type="file"
          onChange={handleFileInput}
          accept={SUPPORTED_FORMATS.join(',')}
          multiple
          disabled={isUploading}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            opacity: 0,
            cursor: isUploading ? 'not-allowed' : 'pointer'
          }}
        />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-sm)' }}>
          {/* Icône */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <svg
              style={{ width: '48px', height: '48px', color: 'var(--v2-text-muted)' }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>

          {/* Texte */}
          <div>
            <p style={{ fontSize: '1.125rem', fontWeight: 500, color: 'var(--v2-text-secondary)' }}>
              Glissez des images ici
            </p>
            <p style={{ fontSize: '0.875rem', color: 'var(--v2-text-muted)', marginTop: '4px' }}>
              ou cliquez pour parcourir (sélection multiple possible)
            </p>
          </div>

          {/* Formats supportés */}
          {!isUploading && (
            <div style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)' }}>
              Formats: {SUPPORTED_FORMATS.join(', ')} • Max 20 MB par image
            </div>
          )}
        </div>
      </div>

      {/* Preview des images sélectionnées */}
      {selectedImages.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--v2-spacing-xs)' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-text-secondary)' }}>
              Images sélectionnées ({selectedImages.length})
            </h3>
            <button
              onClick={() => {
                previewUrls.forEach(url => URL.revokeObjectURL(url))
                setSelectedImages([])
                setPreviewUrls([])
              }}
              disabled={isUploading}
              style={{
                fontSize: '0.75rem',
                color: 'var(--v2-error-text)',
                background: 'transparent',
                border: 'none',
                cursor: isUploading ? 'not-allowed' : 'pointer',
                padding: '4px 8px',
                borderRadius: 'var(--v2-radius-sm)'
              }}
            >
              Tout supprimer
            </button>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
            gap: 'var(--v2-spacing-xs)'
          }}>
            {previewUrls.map((url, index) => (
              <div
                key={index}
                style={{
                  position: 'relative',
                  borderRadius: 'var(--v2-radius-md)',
                  overflow: 'hidden'
                }}
                onMouseEnter={(e) => {
                  const btn = e.currentTarget.querySelector('button')
                  if (btn) btn.style.opacity = '1'
                }}
                onMouseLeave={(e) => {
                  const btn = e.currentTarget.querySelector('button')
                  if (btn) btn.style.opacity = '0'
                }}
              >
                <img
                  src={url}
                  alt={`Preview ${index + 1}`}
                  style={{
                    width: '100%',
                    height: '96px',
                    objectFit: 'cover',
                    border: '1px solid var(--v2-border-secondary)',
                    borderRadius: 'var(--v2-radius-md)'
                  }}
                />
                <button
                  onClick={() => removeImage(index)}
                  disabled={isUploading}
                  style={{
                    position: 'absolute',
                    top: '4px',
                    right: '4px',
                    background: 'var(--v2-error)',
                    color: '#ffffff',
                    borderRadius: 'var(--v2-radius-full)',
                    padding: '4px',
                    border: 'none',
                    cursor: isUploading ? 'not-allowed' : 'pointer',
                    opacity: 0,
                    transition: 'opacity var(--v2-transition-base)'
                  }}
                >
                  <svg style={{ width: '12px', height: '12px' }} fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
                <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  background: 'rgba(0, 0, 0, 0.5)',
                  color: '#ffffff',
                  fontSize: '0.75rem',
                  padding: '4px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  {selectedImages[index].name}
                </div>
              </div>
            ))}
          </div>

          {/* Bouton upload */}
          <div style={{ marginTop: 'var(--v2-spacing-md)' }}>
            <button
              onClick={handleUpload}
              disabled={isUploading || selectedImages.length === 0}
              className="v2-btn"
              style={{
                width: '100%',
                background: 'var(--v2-accent-primary)',
                color: '#ffffff',
                padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
                borderRadius: 'var(--v2-radius-lg)',
                fontWeight: 500,
                cursor: (isUploading || selectedImages.length === 0) ? 'not-allowed' : 'pointer',
                opacity: (isUploading || selectedImages.length === 0) ? 0.5 : 1
              }}
            >
              {isUploading ? 'Upload en cours...' : `Uploader ${selectedImages.length} image(s)`}
            </button>
          </div>
        </div>
      )}

      {/* Message d'erreur */}
      {error && (
        <div style={{
          padding: 'var(--v2-spacing-md)',
          background: 'var(--v2-error-bg)',
          border: '1px solid var(--v2-error-border)',
          borderRadius: 'var(--v2-radius-lg)'
        }}>
          <p style={{ fontSize: '0.875rem', color: 'var(--v2-error-text)' }}>{error}</p>
        </div>
      )}
    </div>
  )
}

export default ImageUpload
