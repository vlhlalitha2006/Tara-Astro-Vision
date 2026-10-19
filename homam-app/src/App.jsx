import { Routes, Route } from 'react-router-dom'
import HomamDetail from './pages/HomamDetail.jsx'
import HomamRedirect from './pages/HomamRedirect.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomamRedirect />} />
      <Route path="/index.html" element={<HomamRedirect />} />
      <Route path=":slug" element={<HomamDetail />} />
      <Route path=":slug/index.html" element={<HomamDetail />} />
    </Routes>
  )
}
