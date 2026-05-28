import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import TargetFactory from './pages/TargetFactory'
import DealScoring from './pages/DealScoring'
import ReviewQueue from './pages/ReviewQueue'
import FieldEvidence from './pages/FieldEvidence'
import AuditTrail from './pages/AuditTrail'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/"         element={<Dashboard />} />
          <Route path="/targets"  element={<TargetFactory />} />
          <Route path="/scoring"  element={<DealScoring />} />
          <Route path="/review"   element={<ReviewQueue />} />
          <Route path="/evidence" element={<FieldEvidence />} />
          <Route path="/audit"    element={<AuditTrail />} />
        </Routes>
      </main>
    </div>
  )
}
