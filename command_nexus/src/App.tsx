import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import CommandCenter from './pages/CommandCenter'
import OCRLab from './pages/OCRLab'
import Documents from './pages/Documents'
import DealDashboard from './pages/DealDashboard'
import TargetFactory from './pages/TargetFactory'
import DealScoring from './pages/DealScoring'
import ReviewQueue from './pages/ReviewQueue'
import FieldEvidence from './pages/FieldEvidence'
import AuditTrail from './pages/AuditTrail'
import Analytics from './pages/Analytics'
import SystemLogs from './pages/SystemLogs'

export default function App() {
  return (
    <div className="flex min-h-screen bg-nx-bg">
      <Sidebar />
      <main className="flex-1 overflow-auto min-h-screen">
        <Routes>
          <Route path="/"         element={<CommandCenter />} />
          <Route path="/ocr"      element={<OCRLab />} />
          <Route path="/docs"     element={<Documents />} />
          <Route path="/deals"    element={<DealDashboard />} />
          <Route path="/targets"  element={<TargetFactory />} />
          <Route path="/scoring"  element={<DealScoring />} />
          <Route path="/review"   element={<ReviewQueue />} />
          <Route path="/evidence" element={<FieldEvidence />} />
          <Route path="/audit"    element={<AuditTrail />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/logs"     element={<SystemLogs />} />
        </Routes>
      </main>
    </div>
  )
}
