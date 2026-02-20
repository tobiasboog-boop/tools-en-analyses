import { useState, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useOpname, useRegels, useBatchUpdateRegels, useBereken } from '../hooks/useOpnames'
import CurrencyDisplay from '../components/shared/CurrencyDisplay'
import type { RegelUpdate } from '../types/opname'

interface Props {
  klantnummer: number
}

export default function ParagraafOpnamePage({ klantnummer }: Props) {
  const { opnameKey } = useParams<{ opnameKey: string }>()
  const navigate = useNavigate()
  const key = Number(opnameKey)

  const { data: opname } = useOpname(klantnummer, key)
  const { data: allRegels, isLoading } = useRegels(klantnummer, key)
  const batchUpdate = useBatchUpdateRegels(klantnummer, key)
  const bereken = useBereken(klantnummer, key)

  // Filter only paragraaf regels (not deelproject)
  const regels = allRegels?.filter((r) => r.deelproject_jn === 'N') || []

  // Local state for PG values (for instant feedback before save)
  const [localPG, setLocalPG] = useState<Record<number, Partial<RegelUpdate>>>({})

  const getPG = useCallback(
    (regelKey: number, field: keyof RegelUpdate) => {
      const local = localPG[regelKey]?.[field]
      if (local !== undefined) return local
      const regel = regels.find((r) => r.regel_key === regelKey)
      if (!regel) return 0
      return regel[field as keyof typeof regel] as number
    },
    [localPG, regels],
  )

  function handlePGChange(regelKey: number, field: keyof RegelUpdate, value: string) {
    const num = Math.max(0, Math.min(100, Number(value) || 0))
    setLocalPG((prev) => ({
      ...prev,
      [regelKey]: { ...prev[regelKey], regel_key: regelKey, [field]: num },
    }))
  }

  async function handleSave() {
    const updates: RegelUpdate[] = Object.values(localPG).filter(
      (u): u is RegelUpdate => !!u.regel_key,
    )
    if (updates.length) {
      await batchUpdate.mutateAsync(updates)
    }
    await bereken.mutateAsync()
    navigate(`/opname/${key}/samenvatting`)
  }

  if (isLoading) return <div className="text-center py-12">Laden...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Paragraaf opname</h1>
          <p className="text-sm text-gray-500">{opname?.hoofdproject}</p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/opname/${key}/deelproject`}
            className="border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50"
          >
            Deelprojecten
          </Link>
          <button
            onClick={handleSave}
            disabled={batchUpdate.isPending || bereken.isPending}
            className="bg-navy-700 text-white px-4 py-2 rounded-lg hover:bg-navy-500 disabled:opacity-50"
          >
            {batchUpdate.isPending || bereken.isPending ? 'Opslaan...' : 'Opslaan & Doorrekenen'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase sticky left-0 bg-gray-50">
                Bestekparagraaf
              </th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Calc. Inkoop</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Geb. Inkoop</th>
              <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase bg-blue-50">% Inkoop</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Calc. Montage</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Geb. Montage</th>
              <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase bg-blue-50">% Montage</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Calc. PG</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Geb. PG</th>
              <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase bg-blue-50">% PG</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {regels.map((regel) => (
              <tr key={regel.regel_key} className="hover:bg-gray-50">
                <td className="px-3 py-2 font-medium text-gray-900 sticky left-0 bg-white">
                  {regel.bestekparagraaf || '-'}
                </td>
                <td className="px-3 py-2 text-right">
                  <CurrencyDisplay value={regel.calculatie_kosten_inkoop} />
                </td>
                <td className="px-3 py-2 text-right">
                  <CurrencyDisplay value={regel.geboekte_kosten_inkoop} />
                </td>
                <td className="px-3 py-2 bg-blue-50">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="w-16 text-center border border-gray-300 rounded px-1 py-1"
                    value={getPG(regel.regel_key, 'percentage_gereed_inkoop')}
                    onChange={(e) =>
                      handlePGChange(regel.regel_key, 'percentage_gereed_inkoop', e.target.value)
                    }
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <CurrencyDisplay value={regel.calculatie_kosten_arbeid_montage} />
                </td>
                <td className="px-3 py-2 text-right">
                  <CurrencyDisplay value={regel.geboekte_kosten_arbeid_montage} />
                </td>
                <td className="px-3 py-2 bg-blue-50">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="w-16 text-center border border-gray-300 rounded px-1 py-1"
                    value={getPG(regel.regel_key, 'percentage_gereed_arbeid_montage')}
                    onChange={(e) =>
                      handlePGChange(regel.regel_key, 'percentage_gereed_arbeid_montage', e.target.value)
                    }
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <CurrencyDisplay value={regel.calculatie_kosten_arbeid_projectgebonden} />
                </td>
                <td className="px-3 py-2 text-right">
                  <CurrencyDisplay value={regel.geboekte_kosten_arbeid_projectgebonden} />
                </td>
                <td className="px-3 py-2 bg-blue-50">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="w-16 text-center border border-gray-300 rounded px-1 py-1"
                    value={getPG(regel.regel_key, 'percentage_gereed_arbeid_projectgebonden')}
                    onChange={(e) =>
                      handlePGChange(regel.regel_key, 'percentage_gereed_arbeid_projectgebonden', e.target.value)
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
