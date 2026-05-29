export default function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 85 ? 'bg-green-500/20 text-green-300 border-green-500/30' :
    score >= 65 ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' :
    score >= 45 ? 'bg-orange-500/20 text-orange-300 border-orange-500/30' :
                  'bg-red-500/20 text-red-300 border-red-500/30'
  return (
    <span className={`badge font-bold border ${color}`}>{score}</span>
  )
}
