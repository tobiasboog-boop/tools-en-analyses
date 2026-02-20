import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import HomePage from './pages/HomePage'
import NieuweOpnamePage from './pages/NieuweOpnamePage'
import ParagraafOpnamePage from './pages/ParagraafOpnamePage'
import DeelprojectOpnamePage from './pages/DeelprojectOpnamePage'
import SamenvattingPage from './pages/SamenvattingPage'

// Hardcoded klantnummer for now - will come from core app auth later
const KLANTNUMMER = 1241

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout klantnummer={KLANTNUMMER} />}>
        <Route index element={<HomePage klantnummer={KLANTNUMMER} />} />
        <Route path="nieuw" element={<NieuweOpnamePage klantnummer={KLANTNUMMER} />} />
        <Route path="opname/:opnameKey/paragraaf" element={<ParagraafOpnamePage klantnummer={KLANTNUMMER} />} />
        <Route path="opname/:opnameKey/deelproject" element={<DeelprojectOpnamePage klantnummer={KLANTNUMMER} />} />
        <Route path="opname/:opnameKey/samenvatting" element={<SamenvattingPage klantnummer={KLANTNUMMER} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
