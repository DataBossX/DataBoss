const STATUS_COLORS: Record<string, string> = {
  // Target status
  Identified:    'bg-blue-100 text-blue-700',
  Contacted:     'bg-indigo-100 text-indigo-700',
  'Under Review':'bg-yellow-100 text-yellow-700',
  'Offer Sent':  'bg-purple-100 text-purple-700',
  Signed:        'bg-green-100 text-green-700',
  Passed:        'bg-slate-100 text-slate-500',
  'On Hold':     'bg-orange-100 text-orange-700',
  // Evidence status
  'Pending Review': 'bg-yellow-100 text-yellow-700',
  Reviewed:         'bg-green-100 text-green-700',
  Flagged:          'bg-red-100 text-red-700',
  // Title clearance
  Clean:            'bg-green-100 text-green-700',
  'Needs Curative': 'bg-yellow-100 text-yellow-700',
  'Probate Pending':'bg-orange-100 text-orange-700',
  Unknown:          'bg-slate-100 text-slate-500',
}

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_COLORS[status] ?? 'bg-slate-100 text-slate-500'}`}>
      {status}
    </span>
  )
}
