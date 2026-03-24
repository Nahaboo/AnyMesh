import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL, generateTexture, pollTaskStatus } from '../utils/api'

const EXAMPLE_PROMPTS = [
  'Carbon Fiber',
  'Old Wood',
  'White Marble',
  'Rusted Metal',
  'Woven Fabric'
]

const Spinner = () => (
  <svg style={{ animation: 'spin 1s linear infinite', width: '16px', height: '16px' }} fill="none" viewBox="0 0 24 24">
    <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

const CheckIcon = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
  </svg>
)

function StepHeader({ number, title, done, active, locked, onClick }) {
  return (
    <div
      onClick={locked ? undefined : onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--v2-spacing-sm)',
        padding: 'var(--v2-spacing-sm) 0',
        cursor: locked ? 'default' : 'pointer',
        opacity: locked ? 0.4 : 1,
        userSelect: 'none',
      }}
    >
      <div style={{
        width: '22px',
        height: '22px',
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '0.7rem',
        fontWeight: 700,
        flexShrink: 0,
        background: done ? '#22c55e' : active ? 'var(--v2-accent-primary)' : 'var(--v2-bg-tertiary)',
        color: done || active ? '#fff' : 'var(--v2-text-muted)',
        border: done || active ? 'none' : '1px solid var(--v2-border-secondary)',
      }}>
        {done ? <CheckIcon /> : number}
      </div>
      <span style={{
        fontSize: '0.875rem',
        fontWeight: 600,
        color: active ? 'var(--v2-text-primary)' : 'var(--v2-text-secondary)',
      }}>
        {title}
      </span>
    </div>
  )
}

function TexturingControls({
  meshInfo,
  // onUnwrapUV,      // kept for debug — UV unwrap available via backend
  // onLoadUnwrapped, // kept for debug
  // onUVCheckerChange, // kept for debug
  onApplyTexture,
  onBakeTexture,
  currentTask,
  isProcessing,
}) {
  const [openStep, setOpenStep] = useState(1)

  // Texture generation state
  const [prompt, setPrompt] = useState('')
  const [generatedTexture, setGeneratedTexture] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [textureError, setTextureError] = useState('')
  const [textureScale, setTextureScale] = useState(3)
  const pollCancelRef = useRef(null)

  useEffect(() => {
    return () => { pollCancelRef.current?.() }
  }, [])

  // Open step 2 when texture is generated
  useEffect(() => {
    if (generatedTexture) setOpenStep(2)
  }, [generatedTexture])

  // UV unwrap state — kept for debug purposes, not shown in UI
  // const uvTaskDone = currentTask?.taskType === 'unwrap_uv' && currentTask?.status === 'completed' && currentTask?.result?.success
  // const uvTaskBusy = isProcessing && currentTask?.taskType === 'unwrap_uv'
  // const uvTaskError = currentTask?.taskType === 'unwrap_uv' && ...

  const bakeTaskDone = currentTask?.taskType === 'bake_texture' && currentTask?.status === 'completed' && currentTask?.result?.success
  const bakeTaskBusy = isProcessing && currentTask?.taskType === 'bake_texture'
  const bakeTaskError = currentTask?.taskType === 'bake_texture' && (currentTask?.status === 'failed' || (currentTask?.status === 'completed' && !currentTask?.result?.success))
    ? (currentTask?.error || currentTask?.result?.error || 'Erreur inconnue') : null

  // UV debug handlers — kept but not wired to UI
  // const handleCheckerChange = (state) => { ... }
  // const handleUnwrap = () => { ... }

  const handleGenerateTexture = async () => {
    if (!prompt.trim()) { setTextureError('Le prompt ne peut pas etre vide'); return }
    setTextureError('')
    setIsGenerating(true)
    try {
      const response = await generateTexture({ prompt: prompt.trim() })
      const poll = pollTaskStatus(response.task_id, (task) => {
        if (task.status === 'completed' && task.result) {
          if (task.result.success) setGeneratedTexture(task.result)
          else setTextureError(task.result.error || 'Erreur de generation')
        } else if (task.status === 'failed') {
          setTextureError(task.error || 'Erreur de generation')
        }
      }, 1000)
      pollCancelRef.current = poll.cancel
      await poll
    } catch (err) {
      setTextureError(err.message || 'Erreur de generation')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleApplyShader = () => {
    if (!generatedTexture || !onApplyTexture) return
    onApplyTexture({ textureId: generatedTexture.texture_id, scale: textureScale, blendSharpness: 2.0 })
  }

  const handleBake = () => {
    if (!generatedTexture || !onBakeTexture || !meshInfo) return
    onBakeTexture({
      filename: meshInfo.filename,
      textureId: generatedTexture.texture_id,
      isGenerated: meshInfo.isGenerated || false,
      isSimplified: meshInfo.isSimplified || false,
      isRetopologized: meshInfo.isRetopologized || false,
      isUVUnwrapped: meshInfo.isUVUnwrapped || false,
    })
  }

  const divider = <div style={{ height: '1px', background: 'var(--v2-border-secondary)', margin: '4px 0' }} />

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>

      {/* ── STEP 1 : Generer texture ───────────────────────── */}
      <StepHeader
        number={1}
        title="Generer texture"
        done={generatedTexture !== null}
        active={openStep === 2}
        locked={false}
        onClick={() => setOpenStep(openStep === 2 ? null : 2)}
      />
      {openStep === 2 && (
        <div style={{ paddingBottom: 'var(--v2-spacing-md)', display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-sm)' }}>
          {generatedTexture ? (
            <>
              <div style={{ borderRadius: 'var(--v2-radius-lg)', overflow: 'hidden', width: '100%', aspectRatio: '1', backgroundImage: `url(${API_BASE_URL}${generatedTexture.texture_url})`, backgroundSize: '50% 50%', backgroundRepeat: 'repeat' }} />
              <div style={{ padding: 'var(--v2-spacing-xs) var(--v2-spacing-sm)', background: 'var(--v2-bg-tertiary)', borderRadius: 'var(--v2-radius-sm)', fontSize: '0.75rem', color: 'var(--v2-text-secondary)' }}>
                <strong>Prompt:</strong> {generatedTexture.prompt}
              </div>
              <div>
                <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-text-secondary)', marginBottom: 'var(--v2-spacing-xs)' }}>
                  <span>Echelle</span><span style={{ color: 'var(--v2-text-muted)' }}>{textureScale}</span>
                </label>
                <input type="range" min="1" max="10" step="0.5" value={textureScale} onChange={(e) => setTextureScale(parseFloat(e.target.value))} style={{ width: '100%', accentColor: 'var(--v2-accent-primary)' }} />
              </div>
              <div style={{ display: 'flex', gap: 'var(--v2-spacing-sm)' }}>
                <button onClick={handleApplyShader} className="v2-btn v2-btn-secondary" style={{ flex: 1, padding: 'var(--v2-spacing-sm)', borderRadius: 'var(--v2-radius-lg)', fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  Preview
                </button>
                <button onClick={() => { setGeneratedTexture(null); setTextureError('') }} className="v2-btn v2-btn-secondary" style={{ padding: 'var(--v2-spacing-sm)', borderRadius: 'var(--v2-radius-lg)', cursor: 'pointer' }}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                </button>
              </div>
            </>
          ) : (
            <>
              <textarea
                value={prompt}
                onChange={(e) => { if (e.target.value.length <= 1000) { setPrompt(e.target.value); setTextureError('') } }}
                placeholder="Ex: Carbon fiber weave, dark and glossy..."
                disabled={isGenerating}
                style={{ width: '100%', minHeight: '72px', padding: 'var(--v2-spacing-sm)', borderRadius: 'var(--v2-radius-lg)', border: `1px solid ${textureError ? '#ef4444' : 'var(--v2-border-primary)'}`, background: 'var(--v2-bg-tertiary)', color: 'var(--v2-text-primary)', fontSize: '0.875rem', resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box' }}
              />
              {textureError && <div style={{ fontSize: '0.75rem', color: '#ef4444' }}>{textureError}</div>}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {EXAMPLE_PROMPTS.map((ex) => (
                  <button key={ex} onClick={() => { setPrompt(ex); setTextureError('') }} disabled={isGenerating} style={{ padding: '3px 8px', borderRadius: '999px', fontSize: '0.72rem', background: 'var(--v2-bg-tertiary)', color: 'var(--v2-text-secondary)', border: '1px solid var(--v2-border-secondary)', cursor: isGenerating ? 'not-allowed' : 'pointer', opacity: isGenerating ? 0.5 : 1 }}>
                    {ex}
                  </button>
                ))}
              </div>
              <button
                onClick={handleGenerateTexture}
                disabled={!prompt.trim() || isGenerating}
                className="v2-btn"
                style={{ width: '100%', background: 'var(--v2-accent-primary)', color: '#fff', padding: 'var(--v2-spacing-sm)', borderRadius: 'var(--v2-radius-lg)', fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--v2-spacing-xs)', cursor: (!prompt.trim() || isGenerating) ? 'not-allowed' : 'pointer', opacity: (!prompt.trim() || isGenerating) ? 0.5 : 1, border: 'none' }}
              >
                {isGenerating ? <><Spinner /><span>Generation en cours...</span></> : <><svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg><span>Generer la texture</span></>}
              </button>
            </>
          )}
        </div>
      )}

      {divider}

      {/* ── STEP 2 : Bake + Export ─────────────────────────── */}
      <StepHeader
        number={2}
        title="Bake + Export"
        done={meshInfo?.isBaked === true}
        active={openStep === 3}
        locked={generatedTexture === null}
        onClick={() => generatedTexture !== null && setOpenStep(openStep === 2 ? null : 2)}
      />
      {openStep === 2 && generatedTexture !== null && (
        <div style={{ paddingBottom: 'var(--v2-spacing-md)', display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-sm)' }}>
          {generatedTexture && (
            <div style={{ borderRadius: 'var(--v2-radius-md)', overflow: 'hidden', width: '100%', aspectRatio: '2/1', backgroundImage: `url(${API_BASE_URL}${generatedTexture.texture_url})`, backgroundSize: '25% 50%', backgroundRepeat: 'repeat' }} />
          )}
          <div style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)' }}>
            Embed la texture dans le GLB via les UVs. Requis pour l'export avec texture.
          </div>
          {bakeTaskError && <div style={{ fontSize: '0.75rem', color: '#ef4444' }}>{bakeTaskError}</div>}
          {bakeTaskDone ? (
            <div style={{ fontSize: '0.8rem', color: '#22c55e', padding: 'var(--v2-spacing-xs) var(--v2-spacing-sm)', background: 'rgba(34,197,94,0.1)', borderRadius: 'var(--v2-radius-sm)' }}>
              Texture bakee avec succes
            </div>
          ) : (
            <button
              onClick={handleBake}
              disabled={bakeTaskBusy}
              className="v2-btn"
              style={{ width: '100%', background: 'var(--v2-accent-primary)', color: '#fff', padding: 'var(--v2-spacing-sm)', borderRadius: 'var(--v2-radius-lg)', fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--v2-spacing-xs)', cursor: bakeTaskBusy ? 'not-allowed' : 'pointer', opacity: bakeTaskBusy ? 0.5 : 1, border: 'none' }}
            >
              {bakeTaskBusy ? <><Spinner /><span>Baking en cours...</span></> : <><svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" /></svg><span>Bake to mesh</span></>}
            </button>
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

export default TexturingControls
