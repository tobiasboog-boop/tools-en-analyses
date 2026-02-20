import { useParams, Link, useNavigate } from 'react-router-dom'
import { useOpname, useOpslaan } from '../hooks/useOpnames'
import CurrencyDisplay from '../components/shared/CurrencyDisplay'
import StatusBadge from '../components/shared/StatusBadge'

interface Props {
  klantnummer: number
}

interface MetricRowProps {
  label: string
  inkoop: number
  montage: number
  projectgebonden: number
  showSign?: boolean
  isPercentage?: boolean
}

function MetricRow({ label, inkoop, montage, projectgebonden, showSign, isPercentage }: MetricRowProps) {
  const total = inkoop + montage + projectgebonden

  if (isPercentage) {
    return (
      <tr className="hover:bg-gray-50">
        <td className="px-4 py-2 text-sm font-medium text-gray-900">{label}</td>
        <td className="px-4 py-2 text-right text-sm">{inkoop.toFixed(1)}%</td>
        <td className="px-4 py-2 text-right text-sm">{montage.toFixed(1)}%</td>
        <td className="px-4 py-2 text-right text-sm">{projectgebonden.toFixed(1)}%</td>
        <td className="px-4 py-2 text-right text-sm font-medium">{total > 0 ? (total / 3).toFixed(1) : '0.0'}%</td>
      </tr>
    )
  }

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-2 text-sm font-medium text-gray-900">{label}</td>
      <td className="px-4 py-2 text-right text-sm"><CurrencyDisplay value={inkoop} showSign={showSign} /></td>
      <td className="px-4 py-2 text-right text-sm"><CurrencyDisplay value={montage} showSign={showSign} /></td>
      <td className="px-4 py-2 text-right text-sm"><CurrencyDisplay value={projectgebonden} showSign={showSign} /></td>
      <td className="px-4 py-2 text-right text-sm font-medium"><CurrencyDisplay value={total} showSign={showSign} /></td>
    </tr>
  )
}

export default function SamenvattingPage({ klantnummer }: Props) {
  const { opnameKey } = useParams<{ opnameKey: string }>()
  const navigate = useNavigate()
  const key = Number(opnameKey)

  const { data: opname, isLoading } = useOpname(klantnummer, key)
  const opslaan = useOpslaan(klantnummer, key)

  async function handleOpslaan() {
    await opslaan.mutateAsync()
    navigate('/')
  }

  if (isLoading || !opname) return <div className="text-center py-12">Laden...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Samenvatting</h1>
          <p className="text-sm text-gray-500">
            {opname.hoofdproject} &middot; <StatusBadge status={opname.autorisatie_status} />
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/opname/${key}/paragraaf`}
            className="border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50"
          >
            Paragrafen bewerken
          </Link>
          <Link
            to={`/opname/${key}/deelproject`}
            className="border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50"
          >
            Deelprojecten bewerken
          </Link>
          {opname.autorisatie_status === 'Concept' && (
            <button
              onClick={handleOpslaan}
              disabled={opslaan.isPending}
              className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {opslaan.isPending ? 'Opslaan...' : 'Definitief opslaan'}
            </button>
          )}
        </div>
      </div>

      {/* Info bar */}
      <div className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <span className="text-gray-500">Boekperiode</span>
          <p className="font-medium">{opname.start_boekdatum} t/m {opname.einde_boekdatum}</p>
        </div>
        <div>
          <span className="text-gray-500">Grondslag calculatie</span>
          <p className="font-medium">{opname.grondslag_calculatie_kosten}</p>
        </div>
        <div>
          <span className="text-gray-500">Grondslag geboekt</span>
          <p className="font-medium">{opname.grondslag_geboekte_kosten}</p>
        </div>
        <div>
          <span className="text-gray-500">Aangemaakt</span>
          <p className="font-medium">{new Date(opname.aanmaakdatum).toLocaleDateString('nl-NL')} door {opname.aanmaker}</p>
        </div>
      </div>

      {/* Financial summary table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-navy-700 text-white">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase">Metric</th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase">Inkoop</th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase">Montage</th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase">Projectgebonden</th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase">Totaal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            <MetricRow label="Calculatie (budget)" inkoop={opname.calculatie_inkoop} montage={opname.calculatie_montage} projectgebonden={opname.calculatie_projectgebonden} />
            <MetricRow label="Geboekt (realisatie)" inkoop={opname.geboekt_inkoop} montage={opname.geboekt_montage} projectgebonden={opname.geboekt_projectgebonden} />

            <tr className="bg-gray-50">
              <td colSpan={5} className="px-4 py-2 text-xs font-bold text-gray-500 uppercase">Berekend</td>
            </tr>

            <MetricRow label="TMB (Te Mogen Besteden)" inkoop={opname.tmb_inkoop} montage={opname.tmb_montage} projectgebonden={opname.tmb_projectgebonden} />
            <MetricRow label="Verschil huidige stand" inkoop={opname.verschil_inkoop_huidige_stand} montage={opname.verschil_montage_huidige_stand} projectgebonden={opname.verschil_projectgebonden_huidige_stand} showSign />
            <MetricRow label="Gemiddeld % gereed" inkoop={opname.gemiddeld_pg_inkoop} montage={opname.gemiddeld_pg_montage} projectgebonden={opname.gemiddeld_pg_projectgebonden} isPercentage />
            <MetricRow label="Verschil einde project" inkoop={opname.verschil_inkoop_einde_project} montage={opname.verschil_montage_einde_project} projectgebonden={opname.verschil_projectgebonden_einde_project} showSign />

            <tr className="bg-gray-50">
              <td colSpan={5} className="px-4 py-2 text-xs font-bold text-gray-500 uppercase">Historisch &amp; Grenzen</td>
            </tr>

            <MetricRow label="Historische verzoeken" inkoop={opname.historische_verzoeken_inkoop} montage={opname.historische_verzoeken_montage} projectgebonden={opname.historische_verzoeken_projectgebonden} />
            <MetricRow label="Ondergrens" inkoop={opname.ondergrens_inkoop} montage={opname.ondergrens_montage} projectgebonden={opname.ondergrens_projectgebonden} />
            <MetricRow label="Bovengrens" inkoop={opname.bovengrens_inkoop} montage={opname.bovengrens_montage} projectgebonden={opname.bovengrens_projectgebonden} />
          </tbody>
        </table>
      </div>

      {/* Opmerking */}
      {opname.opmerking && (
        <div className="bg-white rounded-lg shadow p-4 mt-6">
          <h3 className="font-medium text-gray-900 mb-2">Toelichting</h3>
          <p className="text-sm text-gray-600">{opname.opmerking}</p>
        </div>
      )}
    </div>
  )
}
