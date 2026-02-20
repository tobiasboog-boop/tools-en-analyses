import { Outlet, Link, useLocation } from 'react-router-dom'

interface Props {
  klantnummer: number
}

export default function AppLayout({ klantnummer }: Props) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-navy-700 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold hover:text-navy-50">
            Projectvoortgang Opname
          </Link>
          <div className="text-sm text-navy-50">
            Klantnummer: {klantnummer}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
