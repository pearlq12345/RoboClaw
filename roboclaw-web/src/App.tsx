import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ChatPage from './features/chat/ChatPage'
import ControlPage from './features/control/ControlPage'
import MonitorPage from './features/monitor/MonitorPage'
import SettingsPage from './features/settings/SettingsPage'
import WorkbenchPage from './features/workbench/WorkbenchPage'
import Layout from './shared/components/Layout'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="control" element={<ControlPage />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="workbench" element={<WorkbenchPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
