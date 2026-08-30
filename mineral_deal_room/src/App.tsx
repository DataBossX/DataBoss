import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import HoldRegistry from './pages/HoldRegistry'
import RedTeamTraps from './pages/RedTeamTraps'
import SimulatedJobs from './pages/SimulatedJobs'
import BoundApprovals from './pages/BoundApprovals'
import WellBrain from './pages/WellBrain'
import AuditReceipts from './pages/AuditReceipts'
import TargetFactory from './pages/TargetFactory'
import DealScoring from './pages/DealScoring'
import ReviewQueue from './pages/ReviewQueue'
import FieldEvidence from './pages/FieldEvidence'
import AuditTrail from './pages/AuditTrail'

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/"          element={<Dashboard />} />
          <Route path="/holds"     element={<HoldRegistry />} />
          <Route path="/conflicts" element={<RedTeamTraps />} />
          <Route path="/jobs"      element={<SimulatedJobs />} />
          <Route path="/approvals" element={<BoundApprovals />} />
          <Route path="/wells"     element={<WellBrain />} />
          <Route path="/receipts"  element={<AuditReceipts />} />
          <Route path="/targets"   element={<TargetFactory />} />
          <Route path="/scoring"   element={<DealScoring />} />
          <Route path="/review"    element={<ReviewQueue />} />
          <Route path="/evidence"  element={<FieldEvidence />} />
          <Route path="/audit"     element={<AuditTrail />} />
        </Routes>
      </main>
    </div>
  )
}
