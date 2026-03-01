import { useState } from 'react'
import { API_BASE_URL, generateTexture, pollTaskStatus } from '../utils/api'

const EXAMPLE_PROMPTS = [
  'Carbon Fiber',
  'Old Wood',
  'White Marble',
  'Rusted Metal',
  'Woven Fabric'
]

function TexturingControls({ meshInfo, onApplyTexture, onResetTexture, isProcessing }) {
  const [prompt, setPrompt] = useState('')
  const [generatedTexture, setGeneratedTexture] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState('')
  const [textureScale, setTextureScale] = useState(3)

  const handleGenerateTexture = async () => {
    if (!prompt.trim()) {
      setError('Le prompt ne peut pas etre vide')
      return
    }

    setError('')
    setIsGenerating(true)

    try {
      const response = await generateTexture({ prompt: prompt.trim() })
      const taskId = response.task_id

      await pollTaskStatus(
        taskId,
        (task) => {
          if (task.status === 'completed' && task.result) {
            if (task.result.success) {
              setGeneratedTexture(task.result)
            } else {
              setError(task.result.error || 'Erreur de generation')
            }
          } else if (task.status === 'failed') {
            setError(task.error || 'Erreur de generation')
          }
        },
        1000
      )
    } catch (err) {
      setError(err.message || 'Erreur de generation')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleApply = () => {
    if (!generatedTexture || !onApplyTexture) return
    onApplyTexture({
      textureId: generatedTexture.texture_id,
      scale: textureScale,
      blendSharpness: 2.0
    })
  }

  const handleRegenerate = () => {
    setGeneratedTexture(null)
    setError('')
  }

  const charCount = prompt.length
  const isValid = charCount > 0 && charCount <= 1000
  const busy = isGenerating || isProcessing

  // Step 2: Texture preview + apply
  if (generatedTexture) {
    const textureUrl = `${API_BASE_URL}${generatedTexture.texture_url}`

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
        {/* Tiled 2x2 preview */}
        <div style={{
          borderRadius: 'var(--v2-radius-lg)',
          overflow: 'hidden',
          background: 'var(--v2-bg-tertiary)',
          width: '100%',
          aspectRatio: '1',
          backgroundImage: `url(${textureUrl})`,
          backgroundSize: '50% 50%',
          backgroundRepeat: 'repeat'
        }} />

        {/* Prompt display */}
        <div style={{
          padding: 'var(--v2-spacing-sm)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-sm)',
          fontSize: '0.75rem',
          color: 'var(--v2-text-secondary)'
        }}>
          <strong>Prompt:</strong> {generatedTexture.prompt}
        </div>

        {/* Metadata */}
        <div style={{
          display: 'flex',
          gap: 'var(--v2-spacing-md)',
          fontSize: '0.75rem',
          color: 'var(--v2-text-muted)'
        }}>
          <span>{generatedTexture.image_width}x{generatedTexture.image_height}px</span>
          <span>{Math.round(generatedTexture.generation_time_ms / 1000)}s</span>
        </div>

        {/* Scale slider */}
        <div>
          <label style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)',
            marginBottom: 'var(--v2-spacing-xs)'
          }}>
            <span>Echelle de texture</span>
            <span style={{ color: 'var(--v2-text-muted)' }}>{textureScale}</span>
          </label>
          <input
            type="range"
            min="1"
            max="10"
            step="0.5"
            value={textureScale}
            onChange={(e) => setTextureScale(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }}
          />
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            color: 'var(--v2-text-muted)',
            marginTop: 'var(--v2-spacing-xs)'
          }}>
            <span>1 (gros motifs)</span>
            <span>10 (motifs fins)</span>
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 'var(--v2-spacing-sm)' }}>
          <button
            onClick={handleApply}
            disabled={busy}
            className="v2-btn"
            style={{
              flex: 1,
              background: 'var(--v2-accent-primary)',
              color: '#ffffff',
              padding: 'var(--v2-spacing-sm)',
              borderRadius: 'var(--v2-radius-lg)',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--v2-spacing-xs)',
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
              border: 'none'
            }}
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>Appliquer au mesh</span>
          </button>

          <button
            onClick={handleRegenerate}
            disabled={busy}
            className="v2-btn v2-btn-secondary"
            style={{
              padding: 'var(--v2-spacing-sm)',
              borderRadius: 'var(--v2-radius-lg)',
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1
            }}
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>
    )
  }

  // Step 1: Prompt input
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
      {/* Textarea */}
      <div>
        <label style={{
          display: 'block',
          fontSize: '0.875rem',
          fontWeight: 500,
          color: 'var(--v2-text-secondary)',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          Decrivez le materiau
        </label>
        <textarea
          value={prompt}
          onChange={(e) => {
            if (e.target.value.length <= 1000) {
              setPrompt(e.target.value)
              setError('')
            }
          }}
          placeholder="Ex: Carbon fiber weave, dark and glossy..."
          disabled={busy}
          style={{
            width: '100%',
            minHeight: '80px',
            padding: 'var(--v2-spacing-sm)',
            borderRadius: 'var(--v2-radius-lg)',
            border: `1px solid ${error ? '#ef4444' : 'var(--v2-border-primary)'}`,
            background: 'var(--v2-bg-tertiary)',
            color: 'var(--v2-text-primary)',
            fontSize: '0.875rem',
            resize: 'vertical',
            fontFamily: 'inherit',
            boxSizing: 'border-box'
          }}
        />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 'var(--v2-spacing-xs)',
          fontSize: '0.75rem'
        }}>
          <span style={{ color: error ? '#ef4444' : 'transparent' }}>
            {error || '.'}
          </span>
          <span style={{ color: charCount > 900 ? '#f59e0b' : 'var(--v2-text-muted)' }}>
            {charCount}/1000
          </span>
        </div>
      </div>

      {/* Example chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--v2-spacing-xs)' }}>
        {EXAMPLE_PROMPTS.map((ex) => (
          <button
            key={ex}
            onClick={() => { setPrompt(ex); setError('') }}
            disabled={busy}
            style={{
              padding: '4px 10px',
              borderRadius: '999px',
              fontSize: '0.75rem',
              background: 'var(--v2-bg-tertiary)',
              color: 'var(--v2-text-secondary)',
              border: '1px solid var(--v2-border-secondary)',
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
              transition: 'all var(--v2-transition-base)'
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      {/* Scale slider */}
      <div>
        <label style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.875rem',
          fontWeight: 500,
          color: 'var(--v2-text-secondary)',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          <span>Echelle de texture</span>
          <span style={{ color: 'var(--v2-text-muted)' }}>{textureScale}</span>
        </label>
        <input
          type="range"
          min="1"
          max="10"
          step="0.5"
          value={textureScale}
          onChange={(e) => setTextureScale(parseFloat(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }}
        />
      </div>

      {/* Reset to original texture */}
      {onResetTexture && (
        <button
          onClick={onResetTexture}
          disabled={busy}
          className="v2-btn v2-btn-secondary"
          style={{
            width: '100%',
            padding: 'var(--v2-spacing-sm)',
            borderRadius: 'var(--v2-radius-lg)',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--v2-spacing-xs)',
            cursor: busy ? 'not-allowed' : 'pointer',
            opacity: busy ? 0.5 : 1
          }}
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Texture originale</span>
        </button>
      )}

      {/* Generate button */}
      <button
        onClick={handleGenerateTexture}
        disabled={!isValid || busy}
        className="v2-btn"
        style={{
          width: '100%',
          background: 'var(--v2-accent-primary)',
          color: '#ffffff',
          padding: 'var(--v2-spacing-sm) var(--v2-spacing-md)',
          borderRadius: 'var(--v2-radius-lg)',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--v2-spacing-xs)',
          cursor: (!isValid || busy) ? 'not-allowed' : 'pointer',
          opacity: (!isValid || busy) ? 0.5 : 1,
          border: 'none'
        }}
      >
        {isGenerating ? (
          <>
            <svg style={{ animation: 'spin 1s linear infinite', width: '20px', height: '20px' }} fill="none" viewBox="0 0 24 24">
              <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                style={{ opacity: 0.75 }}
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>Generation en cours...</span>
          </>
        ) : (
          <>
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>Generer la texture</span>
          </>
        )}
      </button>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default TexturingControls
