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
  const MAX_IMAGE_SIZE = 5 * 1024 * 1024 // 5 MB par image

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
        errors.push(`${file.name}: taille trop grande (max 5 MB)`)
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
    <div className="w-full space-y-4">
      {/* Zone de drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center transition-all
          ${isDragging
            ? 'border-purple-500 bg-purple-50'
            : 'border-gray-300 hover:border-gray-400 bg-white'
          }
          ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <input
          type="file"
          onChange={handleFileInput}
          accept={SUPPORTED_FORMATS.join(',')}
          multiple
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />

        <div className="space-y-3">
          {/* Icône */}
          <div className="flex justify-center">
            <svg
              className="w-12 h-12 text-gray-400"
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
            <p className="text-lg font-medium text-gray-700">
              Glissez des images ici
            </p>
            <p className="text-sm text-gray-500 mt-1">
              ou cliquez pour parcourir (sélection multiple possible)
            </p>
          </div>

          {/* Formats supportés */}
          {!isUploading && (
            <div className="text-xs text-gray-400">
              Formats: {SUPPORTED_FORMATS.join(', ')} • Max 5 MB par image
            </div>
          )}
        </div>
      </div>

      {/* Preview des images sélectionnées */}
      {selectedImages.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-700">
              Images sélectionnées ({selectedImages.length})
            </h3>
            <button
              onClick={() => {
                previewUrls.forEach(url => URL.revokeObjectURL(url))
                setSelectedImages([])
                setPreviewUrls([])
              }}
              className="text-xs text-red-600 hover:text-red-800"
              disabled={isUploading}
            >
              Tout supprimer
            </button>
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
            {previewUrls.map((url, index) => (
              <div key={index} className="relative group">
                <img
                  src={url}
                  alt={`Preview ${index + 1}`}
                  className="w-full h-24 object-cover rounded border border-gray-200"
                />
                <button
                  onClick={() => removeImage(index)}
                  className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  disabled={isUploading}
                >
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
                <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 truncate">
                  {selectedImages[index].name}
                </div>
              </div>
            ))}
          </div>

          {/* Bouton upload */}
          <div className="mt-4">
            <button
              onClick={handleUpload}
              disabled={isUploading || selectedImages.length === 0}
              className="w-full bg-purple-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-purple-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isUploading ? 'Upload en cours...' : `Uploader ${selectedImages.length} image(s)`}
            </button>
          </div>
        </div>
      )}

      {/* Message d'erreur */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
  )
}

export default ImageUpload
