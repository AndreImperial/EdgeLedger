import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Shell from './components/Shell'
import { checkHealth, type ApiStatus } from './api'
import { demoSignals } from './data'
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Scanner = lazy(() => import('./pages/Scanner'))
const Trades = lazy(() => import('./pages/Trades'))
const Analytics = lazy(() => import('./pages/Analytics'))
const RiskLab = lazy(() => import('./pages/RiskLab'))
const MarketCalendar = lazy(() => import('./pages/MarketCalendar'))
const Screener = lazy(() => import('./pages/Screener'))
const Playbook = lazy(() => import('./pages/Playbook'))
const Settings = lazy(() => import('./pages/Settings'))
const Goals = lazy(() => import('./pages/Goals'))
const OpenInterest = lazy(() => import('./pages/OpenInterest'))

const initialStatus: ApiStatus = { connected: false, mode: 'demo', message: 'Checking integrated scanner...' }

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>(initialStatus)
  useEffect(() => {
    let active = true
    const refresh = () => checkHealth().then((status) => { if (active) setApiStatus(status) })
    refresh()
    const timer = window.setInterval(refresh, 15_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  return <Shell apiStatus={apiStatus}><Suspense fallback={<div className="route-loading">Loading workspace...</div>}><Routes>
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/scanner" element={<Scanner initialSignals={demoSignals} onStatus={setApiStatus} />} />
    <Route path="/trades" element={<Trades />} />
    <Route path="/analytics" element={<Analytics />} />
    <Route path="/risk-lab" element={<RiskLab />} />
    <Route path="/market-calendar" element={<MarketCalendar />} />
    <Route path="/market-screener" element={<Screener />} />
    <Route path="/open-interest" element={<OpenInterest />} />
    <Route path="/playbook" element={<Playbook />} />
    <Route path="/settings" element={<Settings apiStatus={apiStatus} />} />
    <Route path="/goals" element={<Goals />} />
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes></Suspense></Shell>
}
