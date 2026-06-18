import { useState, useRef } from 'react'
import { SAMPLE_EVIDENCE, SAMPLE_TARGETS } from '../data/sampleData'
import type { Evidence, EvidenceType } from '../types'
import StatusBadge from '../components/StatusBadge'
import { Upload, X, FileText, Download } from 'lucide-react'

const EVIDENCE_TYPES: EvidenceType[] = [
  'Warranty Deed','Oil & Gas Lease','Probate','Affidavit of Heirship',
  'Court Record','Division Order','Assignment','Quit Claim Deed','Mineral Deed','Release',
]

interface LocalUpload {
  id: string
  fileName: string
  type: EvidenceType
  targetId: string
  uploadedAt: string
  fileSize: string
  notes: string
  status: 'Pending Review'
}

export default function FieldEvidence() {
  const [evidence] = useState<Evidence[]>(SAMPLE_EVIDENCE)
  const [uploads, setUploads] = useState<LocalUpload[]>([])
  const [filterTarget, setFilterTarget] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')
  const [selected, setSelected] = useState<Evidence | LocalUpload | null>(null)
  const [showUpload, setShowUpload] = useState(false)

  // Upload form state
  const [uploadForm, setUploadForm] = useState({
    targetId: SAMPLE_TARGETS[0].id,
    type: 'Warranty Deed' as EvidenceType,
    notes: '',
  })
  const [dragActive, setDragActive] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  function getTargetName(id: string) {
    return SAMPLE_TARGETS.find(t => t.id === id)?.ownerName ?? id
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragActive(false)
    const files = Array.from(e.dataTransfer.files).filter(f =>
      f.type === 'application/pdf' || f.type.startsWith('image/')
    )
    setPendingFiles(prev => [...prev, ...files])
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    setPendingFiles(prev => [...prev, ...files])
  }

  function handleUploadSubmit() {
    const now = new Date().toISOString().slice(0, 10)
    const newUploads: LocalUpload[] = pendingFiles.map((f, i) => ({
      id: `U${Date.now()}-${i}`,
      fileName: f.name,
      type: uploadForm.type,
      targetId: uploadForm.targetId,
      uploadedAt: now,
      fileSize: `${(f.size / 1024).toFixed(1)} KB`,
      notes: uploadForm.notes,
      status: 'Pending Review',
    }))
    setUploads(prev => [...prev, ...newUploads])
    setPendingFiles([])
    setUploadForm({ targetId: SAMPLE_TARGETS[0].id, type: 'Warranty Deed', notes: '' })
    setShowUpload(false)
  }

  const allEvidence = [...evidence, ...uploads]
  const filtered = allEvidence.filter(e => {
    const t = filterTarget === 'all' || e.targetId === filterTarget
    const ty = filterType === 'all' || e.type === filterType
    return t && ty
  })

  const types = [...new Set(allEvidence.map(e => e.type))].sort()

  function exportEvidenceCSV() {
    const headers = ['ID','File','Type','Target','County','Book','Page','Instrument #','Recording Date','Grantors','Grantees','Confidence','Status','Notes']
    const rows = evidence.map(e => [
      e.id, e.fileName, e.type, getTargetName(e.targetId), e.county, e.book, e.page,
      e.instrumentNumber, e.recordingDate,
      `"${e.grantors.join('; ')}"`, `"${e.grantees.join('; ')}"`,
      Math.round(e.confidence * 100) + '%', e.status,
      `"${e.notes.replace(/"/g, "'")}"`,
    ])
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `field_evidence_${new Date().toISOString().slice(0,10)}.csv`
    a.click()
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Field Evidence</h1>
          <p className="text-sm text-slate-500">{filtered.length} documents · PDF upload is local-only</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={exportEvidenceCSV}>
            <Download size={14} /> Export CSV
          </button>
          <button className="btn-primary" onClick={() => setShowUpload(true)}>
            <Upload size={14} /> Upload PDF
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select className="input w-48" value={filterTarget} onChange={e => setFilterTarget(e.target.value)}>
          <option value="all">All Targets</option>
          {SAMPLE_TARGETS.map(t => <option key={t.id} value={t.id}>{t.ownerName}</option>)}
        </select>
        <select className="input w-48" value={filterType} onChange={e => setFilterType(e.target.value)}>
          <option value="all">All Types</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Evidence grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map(e => {
          const isLocal = 'fileSize' in e
          const conf = isLocal ? null : (e as Evidence).confidence
          return (
            <div
              key={e.id}
              className="card p-4 cursor-pointer hover:border-orange-300 transition-all"
              onClick={() => setSelected(e)}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center shrink-0">
                  <FileText size={18} className="text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-slate-800 truncate">{e.fileName}</div>
                  <div className="text-xs text-slate-500 truncate">{getTargetName(e.targetId)}</div>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="badge bg-indigo-100 text-indigo-700 text-xs">{e.type}</span>
                    <StatusBadge status={e.status} />
                  </div>
                  {isLocal && (
                    <div className="text-xs text-orange-600 mt-1 font-medium">Local upload · Not submitted</div>
                  )}
                  {conf !== null && (
                    <div className="text-xs text-slate-500 mt-1">
                      Confidence: <span className="font-semibold">{Math.round(conf * 100)}%</span>
                    </div>
                  )}
                </div>
              </div>
              {!isLocal && (e as Evidence).county && (
                <div className="mt-3 text-xs text-slate-500 border-t border-slate-100 pt-2">
                  {(e as Evidence).county} Co. · Book {(e as Evidence).book} Pg {(e as Evidence).page}
                  <span className="mx-1">·</span>{(e as Evidence).recordingDate}
                </div>
              )}
            </div>
          )
        })}
        {filtered.length === 0 && (
          <div className="col-span-3 card p-12 text-center text-slate-400">
            No evidence documents found.
          </div>
        )}
      </div>

      {/* Upload modal */}
      {showUpload && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4" onClick={() => setShowUpload(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between mb-4">
              <h2 className="text-lg font-bold">Upload Evidence Document</h2>
              <button onClick={() => setShowUpload(false)}><X size={18} className="text-slate-400" /></button>
            </div>

            <div
              className={`border-2 border-dashed rounded-xl p-8 text-center mb-4 transition-colors ${dragActive ? 'border-orange-400 bg-orange-50' : 'border-slate-200 hover:border-orange-300'}`}
              onDragOver={e => { e.preventDefault(); setDragActive(true) }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
            >
              <Upload size={32} className="mx-auto text-slate-400 mb-2" />
              <p className="text-sm text-slate-600">Drop PDFs / images here or click to browse</p>
              <p className="text-xs text-slate-400 mt-1">Files stay local — never uploaded to any server</p>
              <input ref={inputRef} type="file" className="hidden" multiple accept=".pdf,image/*" onChange={handleFileInput} />
            </div>

            {pendingFiles.length > 0 && (
              <div className="mb-4 space-y-1">
                {pendingFiles.map((f, i) => (
                  <div key={i} className="flex items-center justify-between bg-slate-50 rounded px-3 py-1.5 text-sm">
                    <span className="truncate">{f.name}</span>
                    <button onClick={() => setPendingFiles(prev => prev.filter((_, j) => j !== i))}>
                      <X size={12} className="text-slate-400 hover:text-red-500" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Linked Target</label>
                <select
                  className="input"
                  value={uploadForm.targetId}
                  onChange={e => setUploadForm(p => ({ ...p, targetId: e.target.value }))}
                >
                  {SAMPLE_TARGETS.map(t => <option key={t.id} value={t.id}>{t.ownerName}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Document Type</label>
                <select
                  className="input"
                  value={uploadForm.type}
                  onChange={e => setUploadForm(p => ({ ...p, type: e.target.value as EvidenceType }))}
                >
                  {EVIDENCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Notes</label>
                <textarea
                  className="input h-20 resize-none"
                  value={uploadForm.notes}
                  onChange={e => setUploadForm(p => ({ ...p, notes: e.target.value }))}
                  placeholder="Notes about this document..."
                />
              </div>
            </div>

            <div className="flex gap-2 mt-4">
              <button className="btn-primary flex-1" onClick={handleUploadSubmit} disabled={pendingFiles.length === 0}>
                <Upload size={14} /> Add {pendingFiles.length > 0 ? `${pendingFiles.length} ` : ''}Document{pendingFiles.length !== 1 ? 's' : ''}
              </button>
              <button className="btn-secondary" onClick={() => setShowUpload(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Detail modal */}
      {selected && !('fileSize' in selected) && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full p-6 overflow-y-auto max-h-[90vh]" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between mb-4">
              <div>
                <div className="font-bold">{selected.fileName}</div>
                <div className="text-xs text-slate-500">{selected.type}</div>
              </div>
              <button onClick={() => setSelected(null)}><X size={18} /></button>
            </div>
            {(() => {
              const e = selected as Evidence
              return (
                <div className="space-y-3 text-sm">
                  <div className="grid grid-cols-2 gap-3">
                    {[['County', e.county],['Book', e.book],['Page', e.page],['Inst. #', e.instrumentNumber],
                      ['Recorded', e.recordingDate],['Executed', e.instrumentDate],
                      ['S-T-R', `${e.section}-${e.township}-${e.range}`],
                      ['Confidence', `${Math.round(e.confidence*100)}%`]
                    ].map(([l,v]) => (
                      <div key={String(l)}>
                        <div className="text-xs text-slate-400 uppercase">{l}</div>
                        <div className="font-medium">{v}</div>
                      </div>
                    ))}
                  </div>
                  <div><div className="text-xs text-slate-400">Grantors</div><div>{e.grantors.join('; ')}</div></div>
                  <div><div className="text-xs text-slate-400">Grantees</div><div>{e.grantees.join('; ')}</div></div>
                  <div><div className="text-xs text-slate-400">Interest Conveyed</div><div>{e.interestConveyed}</div></div>
                  <div><div className="text-xs text-slate-400">Legal Description</div><div className="bg-slate-50 p-2 rounded text-xs">{e.legalDescription}</div></div>
                  {e.notes && <div className="bg-yellow-50 p-2 rounded border border-yellow-200 text-xs text-yellow-800">{e.notes}</div>}
                </div>
              )
            })()}
          </div>
        </div>
      )}
    </div>
  )
}
