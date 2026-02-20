interface Props {
  value: number
  showSign?: boolean
  className?: string
}

export default function CurrencyDisplay({ value, showSign, className = '' }: Props) {
  const formatted = new Intl.NumberFormat('nl-NL', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)

  const colorClass = showSign
    ? value > 0
      ? 'text-red-600'
      : value < 0
        ? 'text-green-600'
        : ''
    : ''

  return <span className={`${colorClass} ${className}`}>{formatted}</span>
}
