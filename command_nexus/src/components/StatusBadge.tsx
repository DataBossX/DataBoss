const STATUS_COLORS: Record<string, string> = {
  Identified:       'bg-blue-500/20 text-blue-300 border border-blue-500/30',
  Contacted:        'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30',
  'Under Review':   'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
  'Offer Sent':     'bg-purple-500/20 text-purple-300 border border-purple-500/30',
  Signed:           'bg-green-500/20 text-green-300 border border-green-500/30',
  Passed:           'bg-slate-500/20 text-slate-400 border border-slate-500/30',
  'On Hold':        'bg-orange-500/20 text-orange-300 border border-orange-500/30',
  'Pending Review': 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
  Reviewed:         'bg-green-500/20 text-green-300 border border-green-500/30',
  Flagged:          'bg-red-500/20 text-red-300 border border-red-500/30',
  Clean:            'bg-green-500/20 text-green-300 border border-green-500/30',
  'Needs Curative': 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
  'Probate Pending':'bg-orange-500/20 text-orange-300 border border-orange-500/30',
  Unknown:          'bg-slate-500/20 text-slate-400 border border-slate-500/30',
}

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge text-xs ${STATUS_COLORS[status] ?? 'bg-slate-500/20 text-slate-400'}`}>
      {status}
    </span>
  )
}
