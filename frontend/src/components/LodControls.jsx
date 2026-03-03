import { getLodZipUrl } from '../utils/api'

const LOD_LABELS = ['LOD0 (original)', 'LOD1 (50%)', 'LOD2 (25%)', 'LOD3 (10%)']
const LOD_COLORS = ['var(--v2-text-primary)', 'var(--v2-accent-primary)', '#f59e0b', 'var(--v2-error-text)']

function LodControls({ meshInfo, onGenerateLod, onLoadLod, currentTask, isProcessing }) {
  const isLodTask = currentTask?.taskType === 'generate_lod'
  const isLodCompleted = isLodTask && currentTask?.status === 'completed'
  const lods = currentTask?.result?.lods || []
  const zipFilename = currentTask?.result?.zip_filename

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!onGenerateLod) return
    const filename = meshInfo.originalFilename || meshInfo.filename
    onGenerateLod({
      filename,
      isGenerated: meshInfo.isGenerated === true,
    })
  }

  return (
    <div style={{
      background: 'var(--v2-bg-secondary)',
      borderRadius: 'var(--v2-radius-lg)',
      boxShadow: 'var(--v2-shadow-md)',
      padding: 'var(--v2-spacing-lg)'
    }}>
      <h2 style={{
        fontSize: '1.25rem',
        fontWeight: 600,
        color: 'var(--v2-text-primary)',
        marginBottom: 'var(--v2-spacing-md)'
      }}>
        Auto-LOD
      </h2>

      <p style={{ fontSize: '0.875rem', color: 'var(--v2-text-tertiary)', marginBottom: 'var(--v2-spacing-md)' }}>
        Génère 4 niveaux de détail automatiquement : LOD0 (original), LOD1 (50%), LOD2 (25%), LOD3 (10%).
      </p>

      {/* Stats triangles actuels */}
      {meshInfo && (
        <div style={{
          background: 'var(--v2-info-bg)',
          borderRadius: 'var(--v2-radius-lg)',
          padding: 'var(--v2-spacing-md)',
          marginBottom: 'var(--v2-spacing-md)',
          fontSize: '0.875rem',
          display: 'flex',
          justifyContent: 'space-between'
        }}>
          <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles actuels :</span>
          <span style={{ fontWeight: 600, color: 'var(--v2-text-primary)' }}>
            {(meshInfo.triangles_count || meshInfo.faces_count || 0).toLocaleString()}
          </span>
        </div>
      )}

      {/* Bouton générer */}
      <form onSubmit={handleSubmit}>
        <button
          type="submit"
          disabled={isProcessing || !meshInfo}
          className="v2-btn v2-btn-primary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
            borderRadius: 'var(--v2-radius-lg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            opacity: (isProcessing || !meshInfo) ? 0.5 : 1,
            cursor: (isProcessing || !meshInfo) ? 'not-allowed' : 'pointer'
          }}
        >
          {isProcessing && isLodTask ? (
            <>
              <svg style={{ animation: 'spin 1s linear infinite', width: '20px', height: '20px' }} fill="none" viewBox="0 0 24 24">
                <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Génération en cours...</span>
            </>
          ) : (
            <>
              <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              <span>Générer les LODs</span>
            </>
          )}
        </button>
      </form>

      {/* Résultats */}
      {isLodCompleted && lods.length > 0 && (
        <div style={{ marginTop: 'var(--v2-spacing-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-sm)' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-text-secondary)', marginBottom: 'var(--v2-spacing-xs)' }}>
            Niveaux générés
          </h3>

          {lods.map((lod) => (
            <div
              key={lod.level}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'var(--v2-bg-tertiary)',
                borderRadius: 'var(--v2-radius-md)',
                padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: LOD_COLORS[lod.level] }}>
                  {LOD_LABELS[lod.level]}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)' }}>
                  {lod.faces_count.toLocaleString()} triangles
                </span>
              </div>
              <button
                type="button"
                onClick={() => onLoadLod(lod.filename)}
                className="v2-btn"
                style={{
                  fontSize: '0.75rem',
                  padding: '4px 10px',
                  borderRadius: 'var(--v2-radius-md)',
                  background: 'var(--v2-accent-primary)',
                  color: '#fff',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: 500
                }}
              >
                Visualiser
              </button>
            </div>
          ))}

          {/* Télécharger ZIP */}
          {zipFilename && (
            <a
              href={getLodZipUrl(zipFilename)}
              download={zipFilename}
              style={{
                marginTop: 'var(--v2-spacing-xs)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--v2-spacing-xs)',
                padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
                borderRadius: 'var(--v2-radius-lg)',
                background: 'var(--v2-success)',
                color: '#fff',
                fontWeight: 500,
                fontSize: '0.875rem',
                textDecoration: 'none'
              }}
            >
              <svg style={{ width: '18px', height: '18px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Télécharger tous les LODs (ZIP)
            </a>
          )}
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default LodControls
