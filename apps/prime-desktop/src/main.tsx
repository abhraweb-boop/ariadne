import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './shell'
import './styles-tokens.css'

const rootEl = document.getElementById('root')

if (!rootEl) {throw new Error('#root missing')}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>
)
