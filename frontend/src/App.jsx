import { useState } from 'react'
import FileUpload from './components/FileUpload'

function App() {
  const [uploadedFile, setUploadedFile] = useState(null)

  const handleUploadSuccess = (fileInfo) => {
    console.log('Fichier uploade:', fileInfo)
    setUploadedFile(fileInfo)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">
            MeshSimplifier
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Simplification et visualisation de maillages 3D
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          {/* Upload Section */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Uploader un fichier 3D
            </h2>
            <FileUpload onUploadSuccess={handleUploadSuccess} />
          </div>

          {/* File Info Section */}
          {uploadedFile && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-800 mb-4">
                Fichier selectionne
              </h2>
              <div className="space-y-2 text-sm text-gray-600">
                <p><span className="font-medium">Nom:</span> {uploadedFile.filename}</p>
                <p><span className="font-medium">Taille:</span> {(uploadedFile.size / 1024).toFixed(2)} KB</p>
                <p><span className="font-medium">Format:</span> {uploadedFile.format}</p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
