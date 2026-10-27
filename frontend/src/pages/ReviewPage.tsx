import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Clock3, FileSearch, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, apiError } from '../lib/api'
import type { DocumentItem } from '../types'

const actions = [
  { decision: 'approved', label: 'Approve', icon: Check, className: 'bg-emerald-600 hover:bg-emerald-700' },
  { decision: 'needs_information', label: 'Request info', icon: Clock3, className: 'bg-amber-500 hover:bg-amber-600' },
  { decision: 'rejected', label: 'Reject', icon: X, className: 'bg-rose-600 hover:bg-rose-700' },
]

export function ReviewPage() {
  const [items, setItems] = useState<DocumentItem[]>([])
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const load = () => api.get<DocumentItem[]>('/review-queue').then(response => setItems(response.data)).catch(error => setError(apiError(error)))
  useEffect(() => { load() }, [])
  async function decide(id: string, decision: string) {
    const note = notes[id]?.trim()
    if (!note || note.length < 2) { setError('Add a short review note before recording a decision.'); return }
    setBusy(id); setError('')
    try { await api.post(`/document/${id}/review`, { decision, note }); setItems(current => current.filter(item => item.id !== id)) }
    catch (err) { setError(apiError(err)) } finally { setBusy('') }
  }
  return <><header className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">HUMAN-IN-THE-LOOP</p><h1 className="mt-2 text-3xl font-bold tracking-tight">Review queue</h1><p className="mt-2 text-slate-500">Resolve documents with risk signals using an accountable, recorded decision.</p></div><div className="glass-card flex items-center gap-3 px-4 py-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-amber-100 text-amber-700"><AlertTriangle size={18}/></span><div><p className="text-lg font-bold">{items.length}</p><p className="text-xs text-slate-500">Awaiting review</p></div></div></header>{error && <p className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<section className="mt-7 space-y-4">{items.map(item => <article key={item.id} className="card overflow-hidden"><div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 p-5"><div><Link to={`/result/${item.id}`} className="font-semibold hover:text-brand-500">{item.original_filename}</Link><p className="mt-1 text-sm capitalize text-slate-500">{item.document_type.replaceAll('_', ' ')} · {new Date(item.created_at).toLocaleString()}</p></div><div className="flex gap-2"><span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700">Risk {item.fraud_probability ?? 0}%</span><span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-bold text-brand-700">Confidence {item.confidence_score ?? 0}</span></div></div><div className="grid gap-5 p-5 lg:grid-cols-[1fr_320px]"><div><p className="text-sm font-medium text-slate-700">Automated assessment</p><p className="mt-2 text-sm leading-6 text-slate-600">{item.explanation}</p><div className="mt-4 flex flex-wrap gap-2">{item.findings.map(finding => <span key={finding.code} className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">{finding.code.replaceAll('_', ' ')}</span>)}</div></div><div><label className="label">Reviewer note</label><textarea value={notes[item.id] || ''} onChange={event => setNotes(current => ({ ...current, [item.id]: event.target.value }))} className="field h-24 resize-none" placeholder="State the evidence and rationale for this decision."/><div className="mt-3 grid grid-cols-3 gap-2">{actions.map(({ decision, label, icon: Icon, className }) => <button key={decision} disabled={busy === item.id} onClick={() => decide(item.id, decision)} className={`inline-flex items-center justify-center gap-1 rounded-lg px-2 py-2 text-xs font-bold text-white transition ${className}`}><Icon size={14}/>{label}</button>)}</div></div></div></article>)}{!items.length && !error && <div className="card grid min-h-64 place-items-center p-8 text-center"><div><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-600"><FileSearch size={23}/></span><h2 className="mt-4 font-semibold">Queue is clear</h2><p className="mt-1 text-sm text-slate-500">Suspicious verifications will appear here for review.</p></div></div>}</section></>
}
