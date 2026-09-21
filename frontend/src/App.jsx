import { useState } from 'react'
import Login from './Login.jsx'
import Workspace from './Workspace.jsx'
import { loadSession, clearSession } from './session.js'

export default function App() {
  const [session, setSession] = useState(() => {
    const s = loadSession()
    return s && s.token ? s : null
  })

  if (!session) return <Login onLogin={setSession} />

  return (
    <Workspace
      session={session}
      onSwitch={() => { clearSession(); setSession(null) }}
      onSessionChange={setSession}
    />
  )
}