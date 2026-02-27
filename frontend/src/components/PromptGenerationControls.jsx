import { useState } from 'react'
import { API_BASE_URL, generateImageFromPrompt, pollTaskStatus } from '../utils/api'

/**
 * PromptGenerationControls - Two-step prompt-to-3D workflow
 * Step 1: User enters prompt → Mamouth.ai generates image
 * Step 2: User previews image → confirms → existing 3D generation via onGenerate
 */
function PromptGenerationControls({ onGenerate, isProcessing, currentTask }) {
  const [prompt, setPrompt] = useState('')
  const [resolution, setResolution] = useState('medium')
  const [provider, setProvider] = useState('trellis')
  const [generatedImage, setGeneratedImage] = useState(null)
  const [isGeneratingImage, setIsGeneratingImage] = useState(false)
  const [error, setError] = useState('')

  const providerInfo = {
    trellis: {
      name: 'TRELLIS',
      description: 'Meilleure qualite, RunPod GPU'
    },
    triposr: {
      name: 'TripoSR (Local)',
      description: 'Gratuit, necessite GPU'
    }
  }

  const handleGenerateImage = async () => {
    if (!prompt.trim()) {
      setError('Le prompt ne peut pas etre vide')
      return
    }

    setError('')
    setIsGeneratingImage(true)

    try {
      const response = await generateImageFromPrompt({ prompt: prompt.trim(), resolution })
      const taskId = response.task_id

      await pollTaskStatus(
        taskId,
        (task) => {
          if (task.status === 'completed' && task.result) {
            if (task.result.success) {
              setGeneratedImage(task.result)
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
      setIsGeneratingImage(false)
    }
  }

  const handleConfirm3D = () => {
    if (!generatedImage || !onGenerate) return

    onGenerate({
      sessionId: generatedImage.session_id,
      resolution,
      provider
    })
  }

  const handleRegenerate = () => {
    setGeneratedImage(null)
    setError('')
  }

  const charCount = prompt.length
  const isValid = charCount > 0 && charCount <= 1000
  const busy = isGeneratingImage || isProcessing

  // Step 2: Image preview + confirm
  if (generatedImage) {
    const imageUrl = `${API_BASE_URL}${generatedImage.image_url}`

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
        {/* Image preview */}
        <div style={{
          borderRadius: 'var(--v2-radius-lg)',
          overflow: 'hidden',
          background: 'var(--v2-bg-tertiary)'
        }}>
          <img
            src={imageUrl}
            alt="Generated"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
        </div>

        {/* Prompt display */}
        <div style={{
          padding: 'var(--v2-spacing-sm)',
          background: 'var(--v2-bg-tertiary)',
          borderRadius: 'var(--v2-radius-sm)',
          fontSize: '0.75rem',
          color: 'var(--v2-text-secondary)'
        }}>
          <strong>Prompt:</strong> {generatedImage.prompt}
        </div>

        {/* Metadata */}
        <div style={{
          display: 'flex',
          gap: 'var(--v2-spacing-md)',
          fontSize: '0.75rem',
          color: 'var(--v2-text-muted)'
        }}>
          <span>{generatedImage.image_width}x{generatedImage.image_height}px</span>
          <span>{Math.round(generatedImage.generation_time_ms / 1000)}s</span>
        </div>

        {/* Provider selector for 3D generation */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--v2-text-secondary)',
            marginBottom: 'var(--v2-spacing-xs)'
          }}>
            Moteur 3D
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--v2-spacing-xs)' }}>
            {['trellis', 'triposr'].map((p) => (
              <button
                key={p}
                onClick={() => setProvider(p)}
                disabled={busy}
                style={{
                  padding: 'var(--v2-spacing-sm)',
                  borderRadius: 'var(--v2-radius-lg)',
                  fontSize: '0.875rem',
                  transition: 'all var(--v2-transition-base)',
                  background: provider === p ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
                  color: provider === p ? '#ffffff' : 'var(--v2-text-secondary)',
                  border: 'none',
                  cursor: busy ? 'not-allowed' : 'pointer',
                  opacity: busy ? 0.5 : 1,
                  textAlign: 'left'
                }}
              >
                <div style={{ fontWeight: 500 }}>{providerInfo[p].name}</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.8, marginTop: '2px' }}>
                  {providerInfo[p].description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 'var(--v2-spacing-sm)' }}>
          <button
            onClick={handleConfirm3D}
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
            <span>Generer 3D</span>
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
          Decrivez votre image
        </label>
        <textarea
          value={prompt}
          onChange={(e) => {
            if (e.target.value.length <= 1000) {
              setPrompt(e.target.value)
              setError('')
            }
          }}
          placeholder="Ex: Un chat orange assis sur un rocher, eclairage naturel, fond blanc..."
          disabled={busy}
          style={{
            width: '100%',
            minHeight: '120px',
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

      {/* Resolution */}
      <div>
        <label style={{
          display: 'block',
          fontSize: '0.875rem',
          fontWeight: 500,
          color: 'var(--v2-text-secondary)',
          marginBottom: 'var(--v2-spacing-xs)'
        }}>
          Resolution de l'image
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--v2-spacing-xs)' }}>
          {['low', 'medium', 'high'].map((res) => (
            <button
              key={res}
              onClick={() => setResolution(res)}
              disabled={busy}
              style={{
                padding: 'var(--v2-spacing-xs) var(--v2-spacing-sm)',
                borderRadius: 'var(--v2-radius-lg)',
                fontSize: '0.875rem',
                fontWeight: 500,
                transition: 'all var(--v2-transition-base)',
                background: resolution === res ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
                color: resolution === res ? '#ffffff' : 'var(--v2-text-secondary)',
                border: 'none',
                cursor: busy ? 'not-allowed' : 'pointer',
                opacity: busy ? 0.5 : 1
              }}
            >
              {res === 'low' && 'Basse'}
              {res === 'medium' && 'Moyenne'}
              {res === 'high' && 'Haute'}
            </button>
          ))}
        </div>
      </div>

      {/* Generate button */}
      <button
        onClick={handleGenerateImage}
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
        {isGeneratingImage ? (
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
            <span>Generer l'image</span>
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

export default PromptGenerationControls
