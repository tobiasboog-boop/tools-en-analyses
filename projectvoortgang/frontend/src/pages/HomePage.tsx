import { Link } from 'react-router-dom'
import { useOpnames, useDeleteOpname } from '../hooks/useOpnames'
import StatusBadge from '../components/shared/StatusBadge'
import CurrencyDisplay from '../components/shared/CurrencyDisplay'

interface Props {
  klantnummer: number
}

export default function HomePage({ klantnummer }: Props) {
  const { data: opnames, isLoading, error } = useOpnames(klantnummer)
  const deleteOpname = useDeleteOpname(klantnummer)

  if (isLoading) return <div className="text-center py-12">Laden...</div>
  if (error) return <div className="text-center py-12 text-red-600">Fout: {(error as Error).message}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projectvoortgang Opnames</h1>
        <Link
          to="/nieuw"
          className="bg-navy-700 text-white px-4 py-2 rounded-lg hover:bg-navy-500 transition-colors"
        >
          + Nieuwe opname
        </Link>
      </div>

      {!opnames?.length ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Nog geen opnames aangemaakt. Klik op "Nieuwe opname" om te beginnen.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Project</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Datum</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Gem. PG</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Totaal TMB</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Acties</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {opnames.map((opname) => (
                <tr key={opname.projectopname_key} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {opname.hoofdproject || `Project ${opname.hoofdproject_key}`}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(opname.aanmaakdatum).toLocaleDateString('nl-NL')}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {opname.gemiddeld_pg_totaal.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <CurrencyDisplay value={opname.tmb_inkoop + opname.tmb_montage + opname.tmb_projectgebonden} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={opname.autorisatie_status} />
                  </td>
                  <td className="px-4 py-3 text-sm space-x-2">
                    <Link
                      to={`/opname/${opname.projectopname_key}/samenvatting`}
                      className="text-navy-700 hover:text-navy-500"
                    >
                      Bekijken
                    </Link>
                    {opname.autorisatie_status === 'Concept' && (
                      <>
                        <Link
                          to={`/opname/${opname.projectopname_key}/paragraaf`}
                          className="text-navy-700 hover:text-navy-500"
                        >
                          Bewerken
                        </Link>
                        <button
                          onClick={() => {
                            if (confirm('Weet je zeker dat je deze opname wilt verwijderen?')) {
                              deleteOpname.mutate(opname.projectopname_key)
                            }
                          }}
                          className="text-red-600 hover:text-red-800"
                        >
                          Verwijder
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
