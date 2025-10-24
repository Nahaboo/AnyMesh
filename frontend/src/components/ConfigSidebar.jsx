import { useState } from 'react'
import FileUpload from './FileUpload'
import ImageUpload from './ImageUpload'

/**
 * Configuration Sidebar - First page of the app
 * Allows user to choose between uploading a 3D file or generating from images
 * Includes options like "Remove background"
 */
function ConfigSidebar({ onConfigComplete }) {
  const [mode, setMode] = useState('upload') // 'upload' or 'generate'
  const [removeBackground, setRemoveBackground] = useState(false)
  const [uploadedData, setUploadedData] = useState(null)

  const handleFileUpload = (meshInfo) => {
    console.log('[ConfigSidebar] File uploaded:', meshInfo)
    setUploadedData({
      type: 'file',
      data: meshInfo
    })
  }

  const handleImagesUpload = (sessionInfo) => {
    console.log('[ConfigSidebar] Images uploaded:', sessionInfo)
    setUploadedData({
      type: 'images',
      data: sessionInfo
    })
  }

  const handleOk = () => {
    if (uploadedData) {
      onConfigComplete({
        ...uploadedData,
        options: {
          removeBackground
        }
      })
    }
  }

  const canProceed = uploadedData !== null

  return (
    <div className="v2-sidebar-config" style={{
      width: 'var(--v2-sidebar-width)',
      height: '100vh',
      background: 'var(--v2-bg-secondary)',
      borderRight: '1px solid var(--v2-border-secondary)',
      display: 'flex',
      flexDirection: 'column',
      padding: 'var(--v2-spacing-lg)'
    }}>
      {/* Header */}
      <div style={{ marginBottom: 'var(--v2-spacing-xl)' }}>
        <h2 style={{
          fontSize: '1.25rem',
          fontWeight: 600,
          color: 'var(--v2-text-primary)',
          marginBottom: 'var(--v2-spacing-sm)'
        }}>
          Any 3D
        </h2>
      </div>

      {/* Mode Selection */}
      <div className="v2-card" style={{ marginBottom: 'var(--v2-spacing-lg)' }}>
        <div className="v2-card-body" style={{ padding: 'var(--v2-spacing-md)' }}>
          <button
            onClick={() => setMode('upload')}
            className={`v2-btn ${mode === 'upload' ? 'v2-btn-primary' : 'v2-btn-secondary'}`}
            style={{
              width: '100%',
              marginBottom: 'var(--v2-spacing-sm)',
              justifyContent: 'flex-start'
            }}
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload 3D file
          </button>

          <button
            onClick={() => setMode('generate')}
            className={`v2-btn ${mode === 'generate' ? 'v2-btn-primary' : 'v2-btn-secondary'}`}
            style={{
              width: '100%',
              justifyContent: 'flex-start'
            }}
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Generate from images
          </button>
        </div>
      </div>

      {/* Upload Area */}
      <div style={{ marginBottom: 'var(--v2-spacing-lg)', flex: 1, overflow: 'auto' }}>
        {mode === 'upload' ? (
          <div>
            <h3 style={{
              fontSize: '0.875rem',
              fontWeight: 600,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-sm)'
            }}>
              Upload your 3D model
            </h3>
            <FileUpload onUploadSuccess={handleFileUpload} />
            {uploadedData?.type === 'file' && (
              <div style={{
                marginTop: 'var(--v2-spacing-md)',
                padding: 'var(--v2-spacing-sm)',
                background: 'var(--v2-bg-tertiary)',
                borderRadius: 'var(--v2-radius-sm)',
                fontSize: '0.75rem',
                color: 'var(--v2-text-secondary)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--v2-spacing-xs)' }}>
                  <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span>File loaded: {uploadedData.data.filename}</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div>
            <h3 style={{
              fontSize: '0.875rem',
              fontWeight: 600,
              color: 'var(--v2-text-secondary)',
              marginBottom: 'var(--v2-spacing-sm)'
            }}>
              Upload images
            </h3>
            <ImageUpload onUploadSuccess={handleImagesUpload} />
            {uploadedData?.type === 'images' && (
              <div style={{
                marginTop: 'var(--v2-spacing-md)',
                padding: 'var(--v2-spacing-sm)',
                background: 'var(--v2-bg-tertiary)',
                borderRadius: 'var(--v2-radius-sm)',
                fontSize: '0.75rem',
                color: 'var(--v2-text-secondary)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--v2-spacing-xs)' }}>
                  <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span>{uploadedData.data.imagesCount} images loaded</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Options Section */}
      <div style={{ marginBottom: 'var(--v2-spacing-xl)' }}>
        <h3 style={{
          fontSize: '0.875rem',
          fontWeight: 600,
          color: 'var(--v2-text-secondary)',
          marginBottom: 'var(--v2-spacing-md)'
        }}>
          Options
        </h3>

        <div className="v2-card">
          <div className="v2-card-body" style={{ padding: 'var(--v2-spacing-md)' }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--v2-spacing-sm)' }}>
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <span style={{ fontSize: '0.875rem', color: 'var(--v2-text-primary)' }}>
                  Remove background
                </span>
              </div>

              <div className="v2-toggle">
                <input
                  type="checkbox"
                  checked={removeBackground}
                  onChange={(e) => setRemoveBackground(e.target.checked)}
                />
                <span className="v2-toggle-slider"></span>
              </div>
            </label>
          </div>
        </div>
      </div>

      {/* OK Button */}
      <button
        onClick={handleOk}
        disabled={!canProceed}
        className="v2-btn v2-btn-primary"
        style={{
          width: '100%',
          padding: 'var(--v2-spacing-md)',
          fontSize: '1rem',
          fontWeight: 600
        }}
      >
        Ok
      </button>
    </div>
  )
}

export default ConfigSidebar
