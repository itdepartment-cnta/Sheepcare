import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// Tipografías autoalojadas (la guía de CNTA prohíbe Google Fonts): Montserrat
// para titulares, Roboto para el cuerpo y JetBrains Mono para identificadores.
import '@fontsource/montserrat/600.css'
import '@fontsource/roboto/400.css'
import '@fontsource/roboto/500.css'
import '@fontsource/roboto/700.css'
import '@fontsource/jetbrains-mono/400.css'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <BrowserRouter>
            <App />
        </BrowserRouter>
    </StrictMode>,
)
