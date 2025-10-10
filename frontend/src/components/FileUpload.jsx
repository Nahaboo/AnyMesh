import { useState } from 'react'

function FileUpload({ onUploadSuccess }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState(null)

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

    // Verifier l'extension
    const fileExt = '.' + file.name.split('.').pop().toLowerCase()
    if (!SUPPORTED_FORMATS.includes(fileExt)) {
      setError(`Format non supporte. Formats acceptes: ${SUPPORTED_FORMATS.join(', ')}`)
      return
    }

    // Pour l'instant, on affiche juste les infos du fichier
    // On connectera au backend dans la prochaine etape
    console.log('Fichier selectionne:', file.name, file.size, 'bytes')

    // Simuler un upload pour tester l'UI
    setIsUploading(true)
    setTimeout(() => {
      setIsUploading(false)
      if (onUploadSuccess) {
        onUploadSuccess({
          filename: file.name,
          size: file.size,
          format: fileExt
        })
      }
    }, 1000)
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

          {/* Formats supportes */}
          <div className="text-xs text-gray-400">
            Formats supportes: {SUPPORTED_FORMATS.join(', ')}
          </div>
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
