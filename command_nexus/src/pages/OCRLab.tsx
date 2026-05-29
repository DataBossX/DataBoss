import { useState, useCallback } from 'react'
import { api } from '../api/client'
import { Upload, FlaskConical, CheckCircle, XCircle, Loader } from 'lucide-react'

type UploadState = 'idle' | 'uploading' | 'success' | 'error' | 'duplicate'

export default function OCRLab() {
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [uploadMsg, setUploadMsg] = useState('')
  const [dragActive, setDragActive] = useState(false)

  async function processFile(file: File) {
    if (!file) return
    setUploadState('uploading')
    setUploadMsg('')
    try {
      const result = await api.upload(file)
      setUploadState('success')
      setUploadMsg(`Document queued: ${result.document_id}`)
    } catch (err: unknown) {
      const e = err as { message?: string }
      if (e.message?.includes('409')) {
        setUploadState('duplicate')
        setUploadMsg('This document has already been uploaded.')
      } else {
        setUploadState('error')
        setUploadMsg(e.message ?? 'Upload failed')
      }
    }
    setTimeout(() => setUploadState('idle'), 5000)
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) processFile(file)
    e.target.value = ''
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) processFile(file)
  }

  const borderColor = dragActive ? 'border-cyan-400 bg-cyan-500/5' :
    uploadState === 'uploading' ? 'border-yellow-400' :
    uploadState === 'success' ? 'border-green-400' :
    uploadState === 'error' || uploadState === 'duplicate' ? 'border-red-400' :
    'border-nx-border hover:border-cyan-500/50'

  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <FlaskConical className="text-cyan-400" size={20} />
          <h1 className="text-xl font-bold text-white tracking-wide">OCR LAB</h1>
        </div>
        <p className="text-sm text-nx-muted">Upload documents for OCR extraction and AI analysis</p>
      </div>

      {/* Drop Zone */}
      <div
        className={`nx-card border-2 border-dashed ${borderColor} rounded-xl p-12 text-center transition-all cursor-pointer`}
        onDragEnter={() => setDragActive(true)}
        onDragOver={e => { e.preventDefault(); setDragActive(true) }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('ocr-file-input')?.click()}
      >
        <input
          id="ocr-file-input"
          type="file"
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.bmp,.tiff"
          onChange={handleFileInput}
        />

        {uploadState === 'idle' && (
          <>
            <Upload className="mx-auto mb-4 text-cyan-400/60" size={40} />
            <p className="text-lg font-semibold text-white mb-2">DROP FILE OR CLICK TO UPLOAD</p>
            <p className="text-sm text-nx-muted">Supports: PDF · PNG · JPG · JPEG · BMP · TIFF</p>
          </>
        )}
        {uploadState === 'uploading' && (
          <>
            <Loader className="mx-auto mb-4 text-yellow-400 animate-spin" size={40} />
            <p className="text-lg font-semibold text-yellow-400">PROCESSING…</p>
            <p className="text-sm text-nx-muted mt-2">Running OCR and AI analysis in background</p>
          </>
        )}
        {uploadState === 'success' && (
          <>
            <CheckCircle className="mx-auto mb-4 text-green-400" size={40} />
            <p className="text-lg font-semibold text-green-400">UPLOAD SUCCESSFUL</p>
            <p className="text-sm text-nx-muted mt-2">{uploadMsg}</p>
          </>
        )}
        {(uploadState === 'error' || uploadState === 'duplicate') && (
          <>
            <XCircle className="mx-auto mb-4 text-red-400" size={40} />
            <p className="text-lg font-semibold text-red-400">
              {uploadState === 'duplicate' ? 'DUPLICATE DOCUMENT' : 'UPLOAD FAILED'}
            </p>
            <p className="text-sm text-nx-muted mt-2">{uploadMsg}</p>
          </>
        )}
      </div>

      {/* Processing Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'Step 1 – OCR Engine', desc: 'Extracts raw text from your document with confidence scoring' },
          { label: 'Step 2 – AI Analysis', desc: 'Available LLMs analyze extracted text (GPT-4, Claude, Gemini)' },
          { label: 'Step 3 – Storage', desc: 'Results saved to local SQLite database, viewable in Document Library' },
        ].map(({ label, desc }) => (
          <div key={label} className="nx-card p-4">
            <div className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-2">{label}</div>
            <div className="text-sm text-nx-muted">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
