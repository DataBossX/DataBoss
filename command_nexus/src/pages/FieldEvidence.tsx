import { useState, useRef } from 'react'
import { SAMPLE_EVIDENCE, SAMPLE_TARGETS } from '../data/sampleData'
import type { Evidence, EvidenceType } from '../types'
import StatusBadge from '../components/StatusBadge'
import { Upload, FolderOpen, X, FileText } from 'lucide-react'

const EVIDENCE_TYPES: EvidenceType[] = [
  'Warranty Deed','Oil & Gas Lease','Probate','Affidavit of Heirship',
  'Court Record','Division Order','Assignment','Quit Claim Deed','Mineral Deed','Release',
]

interface LocalUpload {
  id: string; fileName: string; type: EvidenceType
  targetId: string; uploadedAt: string; fileSize: string; notes: string
  status: 'Pending Review'
}

export default function FieldEvidence() {
  const [uploads, setUploads] = useState<LocalUpload[]>([])
  const [filterTarget, setFilterTarget] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [showUpload, setShowUpload] = useState(false)
  const [form, setForm] = useState({ targetId: SAMPLE_TARGETS[0].id, type: 'Warranty Deed' as EvidenceType, notes: '' })
  const [dragActive, setDragActive] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  function getTargetName(id: string) {
    return SAMPLE_TARGETS.find(t => t.id === id)?.ownerName ?? id
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault(); setDragActive(false)
    const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf' || f.type.startsWith('image/'))
    setPendingFiles(prev => [...prev, ...files])
  }

  function handleSubmit() {
    const now = new Date().toISOString().slice(0, 10)
    const newUploads = pendingFiles.map(f => ({
      id: `LU-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      fileName: f.name, type: form.type, targetId: form.targetId,
      uploadedAt: now, fileSize: `${(f.size / 1024).toFixed(1)} KB`,
      notes: form.notes, status: 'Pending Review' as const,
    }))
    setUploads(prev => [...newUploads, ...prev])
    setPendingFiles([]); setShowUpload(false)
    setForm({ targetId: SAMPLE_TARGETS[0].id, type: 'Warranty Deed', notes: '' })
  }

  const TYPES_IN_SAMPLE = [...new Set(SAMPLE_EVIDENCE.map(e => e.type))].sort()

  const allEvidence = [...uploads.map(u => ({ ...u, county: '—', book: '—', page: '—', instrumentNumber: '—', grantors: [], grantees: [], recordingDate: '—', instrumentDate: '—', legalDescription: '—', confidence: 0, section: '—', township: '—', range: '—', interestConveyed: '—' })), ...SAMPLE_EVIDENCE]

  const filtered = allEvidence.filter(e =>
    (filterTarget === 'all' || e.targetId === filterTarget) &&
    (filterType === 'all' || e.type === filterType)
  )

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FolderOpen className="text-cyan-400" size={20} />
            <h1 className="text-xl font-bold text-white tracking-wide">FIELD EVIDENCE</h1>
          </div>
          <p className="text-sm text-nx-muted">{filtered.length} documents · {uploads.length} local uploads</p>
        </div>
        <button className="btn-cyan" onClick={() => setShowUpload(true)}>
          <Upload size={14} /> Upload Evidence
        </button>
      </div>

      <div className="flex gap-3">
        <select className="nx-select w-56" value={filterTarget} onChange={e => setFilterTarget(e.target.value)}>
          <option value="all">All Targets</option>
          {SAMPLE_TARGETS.map(t => <option key={t.id} value={t.id}>{t.ownerName}</option>)}
        </select>
        <select className="nx-select w-48" value={filterType} onChange={e => setFilterType(e.target.value)}>
          <option value="all">All Types</option>
          {TYPES_IN_SAMPLE.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="nx-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="nx-th">File</th>
              <th className="nx-th">Type</th>
              <th className="nx-th">Target</th>
              <th className="nx-th">County</th>
              <th className="nx-th">Inst. #</th>
              <th className="nx-th">Recorded</th>
              <th className="nx-th">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id} className="hover:bg-nx-card/60">
                <td className="nx-td font-medium text-white">
                  <div className="flex items-center gap-2">
                    <FileText size={13} className="text-cyan-400/60 shrink-0" />
                    {e.fileName}
                  </div>
                </td>
                <td className="nx-td"><span className="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs">{e.type}</span></td>
                <td className="nx-td text-nx-muted">{getTargetName(e.targetId)}</td>
                <td className="nx-td text-nx-muted">{e.county}</td>
                <td className="nx-td font-mono text-xs text-nx-muted">{e.instrumentNumber}</td>
                <td className="nx-td text-nx-muted">{e.recordingDate}</td>
                <td className="nx-td"><StatusBadge status={e.status} /></td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={7} className="nx-td text-center text-nx-muted py-10">No evidence files</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showUpload && (
        <div className="fixed inset-0 bg-black/70 z-40 flex items-center justify-center p-4" onClick={() => setShowUpload(false)}>
          <div className="bg-nx-card border border-nx-bordHi/40 rounded-xl p-6 max-w-lg w-full shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-5">
              <h2 className="font-bold text-white text-lg">Upload Evidence</h2>
              <button onClick={() => setShowUpload(false)} className="text-nx-muted hover:text-white"><X size={18} /></button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-nx-muted uppercase block mb-1">Target</label>
                <select className="nx-select w-full" value={form.targetId} onChange={e => setForm(f => ({ ...f, targetId: e.target.value }))}>
                  {SAMPLE_TARGETS.map(t => <option key={t.id} value={t.id}>{t.ownerName}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-nx-muted uppercase block mb-1">Document Type</label>
                <select className="nx-select w-full" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value as EvidenceType }))}>
                  {EVIDENCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>

              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${dragActive ? 'border-cyan-400 bg-cyan-500/5' : 'border-nx-border hover:border-cyan-500/50'}`}
                onDragEnter={() => setDragActive(true)}
                onDragOver={e => { e.preventDefault(); setDragActive(true) }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
              >
                <input ref={inputRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg" multiple onChange={e => setPendingFiles(prev => [...prev, ...Array.from(e.target.files ?? [])])} />
                <Upload className="mx-auto mb-2 text-cyan-400/60" size={28} />
                <p className="text-sm text-nx-text">Drop files or click to browse</p>
                <p className="text-xs text-nx-muted mt-1">PDF, PNG, JPG</p>
              </div>

              {pendingFiles.length > 0 && (
                <div className="space-y-1">
                  {pendingFiles.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-sm bg-nx-bg border border-nx-border rounded-lg px-3 py-2">
                      <span className="text-nx-text">{f.name}</span>
                      <button onClick={() => setPendingFiles(prev => prev.filter((_, j) => j !== i))} className="text-nx-muted hover:text-red-400"><X size={14} /></button>
                    </div>
                  ))}
                </div>
              )}

              <div>
                <label className="text-xs text-nx-muted uppercase block mb-1">Notes</label>
                <textarea className="nx-input w-full h-20 resize-none" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
              </div>

              <div className="flex gap-2 pt-2">
                <button className="btn-cyan flex-1" disabled={pendingFiles.length === 0} onClick={handleSubmit}>
                  <Upload size={14} /> Upload {pendingFiles.length > 0 ? `(${pendingFiles.length})` : ''}
                </button>
                <button className="btn-ghost" onClick={() => setShowUpload(false)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
