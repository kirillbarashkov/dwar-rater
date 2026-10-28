import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from './hooks/useAuth'
import App from './App'
import { initTheme } from './utils/theme'
import './styles/globals.css'

// Тема применяется до первого рендера: страницы без Header (/admin, /about)
// иначе остаются в теме по умолчанию независимо от выбора пользователя.
initTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
)
