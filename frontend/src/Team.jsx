import { useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHeader, Badge } from './ui.jsx'

const ROLE_BADGE = { ADMIN: 'bg-emerald-50 text-emerald-700', RECRUITER: 'bg-blue-50 text-blue-700' }

export default function Team({ session }) {
  const [members, setMembers] = useState([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('RECRUITER')
  const [busy, setBusy] = useState(false)
  const isAdmin = session.role === 'ADMIN'

  useEffect(() => {
    api('/api/team').then(setMembers).catch(err => alert(err.message))
  }, [])

  async function add(e) {
    e.preventDefault(); setBusy(true)
    try {
      setMembers(await api('/api/team/members', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, role })
      }))
      setEmail(''); setRole('RECRUITER')
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function changeRole(userId, role) {
    try {
      setMembers(await api(`/api/team/members/${userId}/role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role })
      }))
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader eyebrow="Organization Access" title="Team & Roles"
        description={isAdmin
          ? 'Members are added by email. You are an admin and can add members or change roles.'
          : 'Only admins can manage the team. Here is the current roster.'} />

      {isAdmin && (
        <form onSubmit={add} className="bg-white border border-slate-200 rounded-lg p-4 mb-6 flex gap-3 items-end max-sm:flex-col">
          <label className="flex-1 block">
            <span className="label">Email of an existing account</span>
            <input value={email} onChange={e => setEmail(e.target.value)} type="email" required
              placeholder="teammate@company.com"
              className="input" />
          </label>
          <label className="block">
            <span className="label">Role</span>
            <select value={role} onChange={e => setRole(e.target.value)} className="input">
              <option value="RECRUITER">Recruiter</option>
              <option value="ADMIN">Admin</option>
            </select>
          </label>
          <button className="btn-primary" disabled={busy}>Add member</button>
        </form>
      )}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-200">
              <th className="px-4 py-3 font-semibold">Email</th>
              <th className="px-4 py-3 font-semibold">Role</th>
              {isAdmin && <th className="px-4 py-3 font-semibold">Change role</th>}
            </tr>
          </thead>
          <tbody>
            {members.map(m => (
              <tr key={m.id} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-3">
                  <span className="font-medium text-slate-800">{m.email}</span>
                  {m.id === session.user.id && <span className="text-xs text-slate-400 ml-2">(you)</span>}
                </td>
                <td className="px-4 py-3">
                  <Badge className={ROLE_BADGE[m.role] || 'bg-slate-100 text-slate-600'}>{m.role}</Badge>
                </td>
                {isAdmin && (
                  <td className="px-4 py-3">
                    {m.id === session.user.id
                      ? <span className="text-xs text-slate-400">You cannot change your own role.</span>
                      : (
                        <select
                          value={m.role}
                          onChange={e => changeRole(m.id, e.target.value)}
                          className="px-2 py-1 border border-slate-300 rounded text-xs bg-white"
                        >
                          <option value="RECRUITER">Recruiter</option>
                          <option value="ADMIN">Admin</option>
                        </select>
                      )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  )
}