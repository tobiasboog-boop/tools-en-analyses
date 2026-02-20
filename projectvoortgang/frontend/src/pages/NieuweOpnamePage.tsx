import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useHoofdprojecten } from '../hooks/useDWH'
import { useCreateOpname, usePopulateRegels } from '../hooks/useOpnames'

interface Props {
  klantnummer: number
}

const GRONDSLAG_CALCULATIE_OPTIONS = ['Kostprijs', 'Verrekenprijs']
const GRONDSLAG_GEBOEKT_OPTIONS = [
  'Verrekenprijs (definitief + onverwerkt)',
  'Verrekenprijs (definitief)',
  'Kostprijs (definitief)',
]
const PARAGRAAF_NIVEAU_OPTIONS = [1, 2, 3, 4]

export default function NieuweOpnamePage({ klantnummer }: Props) {
  const navigate = useNavigate()
  const { data: projecten, isLoading } = useHoofdprojecten(klantnummer)
  const createOpname = useCreateOpname(klantnummer)
  const populateRegels = usePopulateRegels(klantnummer)

  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    hoofdproject_key: 0,
    hoofdproject: '',
    grondslag_calculatie_kosten: 'Kostprijs',
    grondslag_geboekte_kosten: 'Verrekenprijs (definitief + onverwerkt)',
    groepering_paragraafniveau: 1,
  })

  const selectedProject = projecten?.find((p) => p.project_key === form.hoofdproject_key)

  async function handleCreate() {
    const opname = await createOpname.mutateAsync({
      ...form,
      start_boekdatum: selectedProject?.start_boekdatum,
      einde_boekdatum: selectedProject?.einde_boekdatum,
    })

    await populateRegels.mutateAsync(opname.projectopname_key)
    navigate(`/opname/${opname.projectopname_key}/paragraaf`)
  }

  if (isLoading) return <div className="text-center py-12">Projecten laden...</div>

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Nieuwe opname</h1>

      {/* Progress bar */}
      <div className="flex items-center mb-8 gap-2">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className={`flex-1 h-2 rounded-full ${s <= step ? 'bg-navy-700' : 'bg-gray-200'}`}
          />
        ))}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        {step === 1 && (
          <div>
            <h2 className="text-lg font-semibold mb-4">Stap 1: Selecteer project</h2>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Hoofdproject
            </label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 mb-4"
              value={form.hoofdproject_key}
              onChange={(e) => {
                const key = Number(e.target.value)
                const proj = projecten?.find((p) => p.project_key === key)
                setForm({
                  ...form,
                  hoofdproject_key: key,
                  hoofdproject: proj?.project_naam || '',
                })
              }}
            >
              <option value={0}>-- Selecteer een project --</option>
              {projecten?.map((p) => (
                <option key={p.project_key} value={p.project_key}>
                  {p.project_naam} ({p.projectfase})
                </option>
              ))}
            </select>

            {selectedProject && (
              <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
                <p>Boekperiode: {selectedProject.start_boekdatum} t/m {selectedProject.einde_boekdatum}</p>
              </div>
            )}

            <div className="mt-6 flex justify-end">
              <button
                disabled={!form.hoofdproject_key}
                onClick={() => setStep(2)}
                className="bg-navy-700 text-white px-6 py-2 rounded-lg hover:bg-navy-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Volgende
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 className="text-lg font-semibold mb-4">Stap 2: Instellingen</h2>

            <label className="block text-sm font-medium text-gray-700 mb-2">
              Grondslag calculatie kosten
            </label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 mb-4"
              value={form.grondslag_calculatie_kosten}
              onChange={(e) => setForm({ ...form, grondslag_calculatie_kosten: e.target.value })}
            >
              {GRONDSLAG_CALCULATIE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>

            <label className="block text-sm font-medium text-gray-700 mb-2">
              Grondslag geboekte kosten
            </label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 mb-4"
              value={form.grondslag_geboekte_kosten}
              onChange={(e) => setForm({ ...form, grondslag_geboekte_kosten: e.target.value })}
            >
              {GRONDSLAG_GEBOEKT_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>

            <label className="block text-sm font-medium text-gray-700 mb-2">
              Groepering paragraafniveau
            </label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 mb-4"
              value={form.groepering_paragraafniveau}
              onChange={(e) => setForm({ ...form, groepering_paragraafniveau: Number(e.target.value) })}
            >
              {PARAGRAAF_NIVEAU_OPTIONS.map((n) => (
                <option key={n} value={n}>Niveau {n}</option>
              ))}
            </select>

            <div className="mt-6 flex justify-between">
              <button onClick={() => setStep(1)} className="text-gray-600 hover:text-gray-900">
                Terug
              </button>
              <button
                onClick={() => setStep(3)}
                className="bg-navy-700 text-white px-6 py-2 rounded-lg hover:bg-navy-500"
              >
                Volgende
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 className="text-lg font-semibold mb-4">Stap 3: Bevestigen</h2>

            <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
              <p><span className="font-medium">Project:</span> {form.hoofdproject}</p>
              <p><span className="font-medium">Boekperiode:</span> {selectedProject?.start_boekdatum} t/m {selectedProject?.einde_boekdatum}</p>
              <p><span className="font-medium">Calculatie grondslag:</span> {form.grondslag_calculatie_kosten}</p>
              <p><span className="font-medium">Geboekte kosten grondslag:</span> {form.grondslag_geboekte_kosten}</p>
              <p><span className="font-medium">Paragraafniveau:</span> Niveau {form.groepering_paragraafniveau}</p>
            </div>

            <div className="mt-6 flex justify-between">
              <button onClick={() => setStep(2)} className="text-gray-600 hover:text-gray-900">
                Terug
              </button>
              <button
                onClick={handleCreate}
                disabled={createOpname.isPending || populateRegels.isPending}
                className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {createOpname.isPending || populateRegels.isPending ? 'Aanmaken...' : 'Opname aanmaken'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
