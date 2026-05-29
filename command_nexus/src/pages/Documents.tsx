import { useState, useEffect } from 'react'
import { api, Document, DocumentDetail } from '../api/client'
import { FileText, X, RefreshCw } from 'lucide-react'

const STATUS_STYLE: Record<string, string> = {
  uploaded:   'bg-blue-500/20 text-blue-300',
  processing: 'bg-yellow-500/20 text-yellow-300 animate-pulse',
  completed:  'bg-green-500/20 text-green-300',
  failed:     'bg-red-500/20 text-red-300',
}

export default function Documents() {
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<DocumentDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  async function load() {
    try {
      const d = await api.documents()
      setDocs(d)
    } finally {
      setLoading(false)
    }
  }

  async function openDoc(doc: Document) {
    setLoadingDetail(true)
    try {
      const detail = await api.document(doc.id)
      setSelected(detail)
    } finally {
      setLoadingDetail(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileText className="text-cyan-400" size={20} />
            <h1 className="text-xl font-bold text-white tracking-wide">DOCUMENT LIBRARY</h1>
          </div>
          <p className="text-sm text-nx-muted">{docs.length} documents · auto-refreshes every 5s</p>
        </div>
        <button onClick={load} className="btn-cyan">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="text-nx-muted text-sm animate-pulse">Loading documents…</div>
      ) : docs.length === 0 ? (
        <div className="nx-card p-12 text-center text-nx-muted">No documents yet — upload one in OCR Lab</div>
      ) : (
        <div className="nx-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="nx-th">Filename</th>
                <th className="nx-th">Status</th>
                <th className="nx-th">Size</th>
                <th className="nx-th">Uploaded</th>
                <th className="nx-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id} className="hover:bg-nx-card/60 cursor-pointer" onClick={() => openDoc(doc)}>
                  <td className="nx-td font-medium text-white">{doc.filename}</td>
                  <td className="nx-td">
                    <span className={`badge ${STATUS_STYLE[doc.status] ?? ''}`}>{doc.status.toUpperCase()}</span>
                  </td>
                  <td className="nx-td text-nx-muted">{(doc.file_size / 1024).toFixed(1)} KB</td>
                  <td className="nx-td text-nx-muted">{new Date(doc.upload_time).toLocaleString()}</td>
                  <td className="nx-td">
                    <button className="text-xs text-cyan-400 hover:underline" onClick={e => { e.stopPropagation(); openDoc(doc) }}>
                      View Results
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail Modal */}
      {(loadingDetail || selected) && (
        <div
          className="fixed inset-0 bg-black/70 z-40 flex items-center justify-center p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-nx-card border border-nx-bordHi/40 rounded-xl p-6 max-w-3xl w-full max-h-[85vh] overflow-y-auto shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {loadingDetail ? (
              <div className="text-nx-muted text-sm animate-pulse py-8 text-center">Loading results…</div>
            ) : selected ? (
              <>
                <div className="flex justify-between items-center mb-5">
                  <div>
                    <h2 className="text-lg font-bold text-white">{selected.document.filename}</h2>
                    <p className="text-xs text-nx-muted">{selected.document.id}</p>
                  </div>
                  <button onClick={() => setSelected(null)} className="text-nx-muted hover:text-white">
                    <X size={20} />
                  </button>
                </div>

                {selected.ocr_results.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-3">OCR RESULTS</h3>
                    {selected.ocr_results.map(r => (
                      <div key={r.id} className="bg-nx-bg border border-nx-border rounded-lg p-4">
                        <div className="flex gap-6 text-xs text-nx-muted mb-3">
                          <span>Confidence: <span className="text-green-400 font-bold">{(r.confidence_score * 100).toFixed(1)}%</span></span>
                          <span>Processing: <span className="text-cyan-400">{r.processing_time.toFixed(2)}s</span></span>
                        </div>
                        <div className="text-sm text-nx-text max-h-48 overflow-y-auto font-mono whitespace-pre-wrap bg-black/20 p-3 rounded">
                          {r.cleaned_text}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {selected.llm_analysis.length > 0 && (
                  <div>
                    <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-3">AI ANALYSIS</h3>
                    {selected.llm_analysis.map(a => (
                      <div key={a.id} className="bg-nx-bg border border-nx-border rounded-lg p-4 mb-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-bold text-orange-400 uppercase">{a.model_name}</span>
                          <span className="text-xs text-nx-muted">{a.processing_time.toFixed(2)}s</span>
                        </div>
                        <div className="text-sm text-nx-text leading-relaxed">
                          {a.analysis_result.analysis}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {selected.ocr_results.length === 0 && selected.llm_analysis.length === 0 && (
                  <div className="text-nx-muted text-sm text-center py-8">
                    Processing in progress — check back in a moment
                  </div>
                )}
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
