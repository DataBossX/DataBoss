import { useState } from 'react'
import { INITIAL_RECEIPTS } from '../data/sampleData'
import type { VerificationReceipt } from '../types'
import { FileCode2, ShieldCheck, Download, CheckCircle2, Hash, Copy, Check } from 'lucide-react'

export default function AuditReceipts() {
  const [receipts] = useState<VerificationReceipt[]>(INITIAL_RECEIPTS)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  function copyHash(text: string, id: string) {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2500)
  }

  function downloadReceiptFile(receipt: VerificationReceipt) {
    const json = JSON.stringify(receipt, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${receipt.receiptId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs font-bold rounded bg-purple-100 text-purple-900 border border-purple-300">
              CRYPTOGRAPHIC PROVENANCE P-18
            </span>
            <span className="text-xs font-mono text-slate-500">DIGEST-STRENGTH AUDIT TRAIL</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
            Verification Receipts & Tournament Authority
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Immutable, content-addressed verification receipts proving zero byte mutation, fail-closed sentinels, and exact digest verification.
          </p>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-900 text-white font-mono text-xs flex items-center gap-2">
          <ShieldCheck size={16} className="text-purple-400" />
          <span>SHA-256 Digest Sidecars Verified</span>
        </div>
      </div>

      {/* Receipts Cards */}
      <div className="space-y-4">
        {receipts.map(r => (
          <div key={r.receiptId} className="card p-6 border-slate-300 space-y-4 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 pb-3 border-b border-slate-200">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm font-black text-slate-900">{r.receiptId}</span>
                  <span className="badge bg-purple-100 text-purple-800 font-bold">{r.projectId}</span>
                  <span className="badge bg-emerald-100 text-emerald-800 font-bold">{r.status}</span>
                </div>
                <div className="text-xs text-slate-600 font-mono mt-1">
                  Actor: <strong className="text-slate-900">{r.actor}</strong> · Target: <strong>{r.target}</strong> · Timestamp: {r.timestamp}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadReceiptFile(r)}
                  className="btn-secondary text-xs py-1.5 flex items-center gap-1.5"
                >
                  <Download size={13} /> Export Receipt JSON
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-700 font-medium">{r.details}</p>

            {/* Cryptographic Digests Box */}
            <div className="p-4 rounded-xl bg-slate-950 text-slate-200 font-mono text-xs space-y-2">
              <div className="flex items-center justify-between pb-1 border-b border-slate-800 text-[11px] text-slate-400 uppercase tracking-wider">
                <span>Cryptographic Digest Bindings</span>
                <span className="text-emerald-400 font-bold flex items-center gap-1">
                  <CheckCircle2 size={12} /> Byte-For-Byte Confirmed
                </span>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate">
                    <span className="text-slate-500">INPUT SHA256: </span>
                    <span className="text-slate-300">{r.inputHash}</span>
                  </div>
                  <button
                    onClick={() => copyHash(r.inputHash, `${r.receiptId}-in`)}
                    className="text-slate-400 hover:text-white shrink-0"
                  >
                    {copiedId === `${r.receiptId}-in` ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  </button>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <div className="truncate">
                    <span className="text-slate-500">OUTPUT SHA256: </span>
                    <span className="text-emerald-400 font-bold">{r.outputHash}</span>
                  </div>
                  <button
                    onClick={() => copyHash(r.outputHash, `${r.receiptId}-out`)}
                    className="text-slate-400 hover:text-white shrink-0"
                  >
                    {copiedId === `${r.receiptId}-out` ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
