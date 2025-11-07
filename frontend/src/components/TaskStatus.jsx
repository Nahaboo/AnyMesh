import { useEffect } from 'react'

function TaskStatus({ task, onComplete, activeTool }) {
  useEffect(() => {
    // Notifier le parent quand la tache est completee
    if (task && task.status === 'completed' && onComplete) {
      onComplete(task)
    }
  }, [task, onComplete])

  if (!task) {
    return null
  }

  // Mapper les taskType vers les tools correspondants
  const taskTypeToTool = {
    'simplify': 'simplification',
    'segment': 'segmentation',
    'retopology': 'retopoly',
    'generate': null  // Pas d'outil dédié pour generate
  }

  // N'afficher que si le taskType correspond à l'outil actif
  const taskTool = taskTypeToTool[task.taskType]
  if (taskTool && activeTool && taskTool !== activeTool) {
    return null
  }

  const getStatusStyles = (status) => {
    switch (status) {
      case 'pending':
        return {
          background: 'var(--v2-warning-bg)',
          borderColor: 'var(--v2-warning-border)',
          color: 'var(--v2-warning-text)'
        }
      case 'processing':
        return {
          background: 'var(--v2-info-bg)',
          borderColor: 'var(--v2-info-border)',
          color: 'var(--v2-info-text)'
        }
      case 'completed':
        return {
          background: 'var(--v2-success-bg)',
          borderColor: 'var(--v2-success-border)',
          color: 'var(--v2-success-text)'
        }
      case 'failed':
        return {
          background: 'var(--v2-error-bg)',
          borderColor: 'var(--v2-error-border)',
          color: 'var(--v2-error-text)'
        }
      default:
        return {
          background: 'var(--v2-bg-tertiary)',
          borderColor: 'var(--v2-border-secondary)',
          color: 'var(--v2-text-secondary)'
        }
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return (
          <svg style={{ width: '20px', height: '20px' }} fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
          </svg>
        )
      case 'processing':
        return (
          <svg style={{ width: '20px', height: '20px', animation: 'spin 1s linear infinite' }} fill="none" viewBox="0 0 24 24">
            <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        )
      case 'completed':
        return (
          <svg style={{ width: '20px', height: '20px' }} fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        )
      case 'failed':
        return (
          <svg style={{ width: '20px', height: '20px' }} fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        )
      default:
        return null
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'pending':
        return 'En attente'
      case 'processing':
        return 'En cours de traitement'
      case 'completed':
        return 'Terminé'
      case 'failed':
        return 'Échoué'
      default:
        return status
    }
  }

  const statusStyles = getStatusStyles(task.status)

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
        Statut de la tâche
      </h2>

      {/* Statut */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--v2-spacing-sm)',
        padding: 'var(--v2-spacing-md)',
        borderRadius: 'var(--v2-radius-lg)',
        border: `1px solid ${statusStyles.borderColor}`,
        background: statusStyles.background,
        color: statusStyles.color,
        marginBottom: 'var(--v2-spacing-md)'
      }}>
        {getStatusIcon(task.status)}
        <div style={{ flex: 1 }}>
          <p style={{ fontWeight: 500 }}>{getStatusText(task.status)}</p>
          {task.status === 'processing' && (
            <p style={{ fontSize: '0.875rem', marginTop: '4px' }}>Progression: {task.progress}%</p>
          )}
        </div>
      </div>

      {/* Barre de progression */}
      {task.status === 'processing' && (
        <div style={{ marginBottom: 'var(--v2-spacing-md)' }}>
          <div style={{
            width: '100%',
            background: 'var(--v2-bg-tertiary)',
            borderRadius: 'var(--v2-radius-full)',
            height: '8px'
          }}>
            <div style={{
              background: 'var(--v2-info)',
              height: '8px',
              borderRadius: 'var(--v2-radius-full)',
              transition: 'width 300ms ease',
              width: `${task.progress}%`
            }} />
          </div>
        </div>
      )}

      {/* Erreur */}
      {task.status === 'failed' && task.error && (
        <div style={{
          marginBottom: 'var(--v2-spacing-md)',
          padding: 'var(--v2-spacing-md)',
          background: 'var(--v2-error-bg)',
          border: '1px solid var(--v2-error-border)',
          borderRadius: 'var(--v2-radius-lg)'
        }}>
          <p style={{ fontSize: '0.875rem', color: 'var(--v2-error-text)' }}>{task.error}</p>
        </div>
      )}

      {/* Resultats */}
      {task.status === 'completed' && task.result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--v2-spacing-md)' }}>
          {/* Statistiques */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--v2-spacing-md)' }}>
            <div style={{
              background: 'var(--v2-bg-tertiary)',
              borderRadius: 'var(--v2-radius-lg)',
              padding: 'var(--v2-spacing-md)'
            }}>
              <p style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)', marginBottom: '4px' }}>Original</p>
              <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--v2-text-primary)' }}>
                {task.result.original?.vertices?.toLocaleString()} vertices
              </p>
              <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--v2-text-primary)' }}>
                {task.result.original?.triangles?.toLocaleString()} triangles
              </p>
            </div>

            <div style={{
              background: 'var(--v2-success-bg)',
              borderRadius: 'var(--v2-radius-lg)',
              padding: 'var(--v2-spacing-md)'
            }}>
              <p style={{ fontSize: '0.75rem', color: 'var(--v2-success-text)', marginBottom: '4px' }}>Simplifié</p>
              <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--v2-success-text)' }}>
                {task.result.simplified?.vertices?.toLocaleString()} vertices
              </p>
              <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--v2-success-text)' }}>
                {task.result.simplified?.triangles?.toLocaleString()} triangles
              </p>
            </div>
          </div>

          {/* Reduction */}
          <div style={{
            background: 'var(--v2-info-bg)',
            borderRadius: 'var(--v2-radius-lg)',
            padding: 'var(--v2-spacing-md)'
          }}>
            <p style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--v2-text-secondary)', marginBottom: 'var(--v2-spacing-xs)' }}>Réduction</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--v2-text-tertiary)' }}>Vertices supprimés:</span>
                <span style={{ fontWeight: 600, color: 'var(--v2-info-text)' }}>
                  {(task.result.original?.vertices - task.result.simplified?.vertices)?.toLocaleString()}
                  {task.result.reduction?.vertices_ratio && ` (${(task.result.reduction.vertices_ratio * 100).toFixed(1)}%)`}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--v2-text-tertiary)' }}>Triangles supprimés:</span>
                <span style={{ fontWeight: 600, color: 'var(--v2-info-text)' }}>
                  {(task.result.original?.triangles - task.result.simplified?.triangles)?.toLocaleString()}
                  {task.result.reduction?.triangles_ratio && ` (${(task.result.reduction.triangles_ratio * 100).toFixed(1)}%)`}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Info task ID */}
      <div style={{
        marginTop: 'var(--v2-spacing-md)',
        paddingTop: 'var(--v2-spacing-md)',
        borderTop: '1px solid var(--v2-border-secondary)'
      }}>
        <p style={{ fontSize: '0.75rem', color: 'var(--v2-text-muted)' }}>
          Task ID: <span style={{ fontFamily: 'var(--v2-font-mono)' }}>{task.id}</span>
        </p>
      </div>

      {/* Ajout du keyframes pour l'animation spin */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default TaskStatus
