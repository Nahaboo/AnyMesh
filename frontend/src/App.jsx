function App() {
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
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            Bienvenue !
          </h2>
          <p className="text-gray-600">
            Frontend React fonctionnel avec Tailwind CSS.
          </p>
          <p className="text-gray-600 mt-2">
            Prochaine etape : ajouter l'upload de fichiers et la visualisation 3D.
          </p>
        </div>
      </main>
    </div>
  )
}

export default App
