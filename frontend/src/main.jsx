import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

// ========================================
// VERSION SWITCH
// ========================================
// To revert to the old version, uncomment the line below and comment the current import:
// import App from './components/v1/AppV1.jsx'

// Current version (formerly V2, now main)
import App from './App.jsx'
// ========================================

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
