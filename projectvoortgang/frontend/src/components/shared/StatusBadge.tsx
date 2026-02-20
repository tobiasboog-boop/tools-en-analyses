interface Props {
  status: string
}

const statusColors: Record<string, string> = {
  Concept: 'bg-gray-100 text-gray-700',
  'Ter autorisatie': 'bg-yellow-100 text-yellow-800',
  Geautoriseerd: 'bg-green-100 text-green-800',
}

export default function StatusBadge({ status }: Props) {
  const colorClass = statusColors[status] || 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {status}
    </span>
  )
}
