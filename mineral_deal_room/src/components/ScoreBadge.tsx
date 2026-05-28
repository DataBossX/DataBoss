export default function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 85 ? 'bg-green-100 text-green-700' :
    score >= 65 ? 'bg-yellow-100 text-yellow-700' :
    score >= 45 ? 'bg-orange-100 text-orange-700' :
                  'bg-red-100 text-red-700'
  return (
    <span className={`badge font-bold ${color}`}>{score}</span>
  )
}
