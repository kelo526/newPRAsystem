import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './Login.jsx'
import LoginPortal from './LoginPortal.jsx'
import Report from './Report.jsx'
import ExportDemo from './ExportDemo.jsx'
import ExportView from './ExportView.jsx'

function RequireAuth({ children }) {
  const token = localStorage.getItem('demo_token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/portal" element={<LoginPortal />} />
      <Route
        path="/report"
        element={
          <RequireAuth>
            <Report />
          </RequireAuth>
        }
      />
      <Route
        path="/export-demo"
        element={
          <RequireAuth>
            <ExportDemo />
          </RequireAuth>
        }
      />
      <Route
        path="/export-view"
        element={
          <RequireAuth>
            <ExportView />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/report" replace />} />
    </Routes>
  )
}
