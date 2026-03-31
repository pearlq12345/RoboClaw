import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ChatView from './views/ChatView'
import SettingsView from './views/SettingsView'
import DataCollectionView from './views/DataCollectionView'
import Layout from './components/Layout'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatView />} />
          <Route path="data" element={<DataCollectionView />} />
          <Route path="settings" element={<SettingsView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
