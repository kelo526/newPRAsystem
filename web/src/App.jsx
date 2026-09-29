import React from 'react'
import { HashRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  CloudServerOutlined,
  ApiOutlined,
  ScheduleOutlined,
  AppstoreOutlined,
  BulbOutlined
} from '@ant-design/icons'
import Systems from './pages/Systems.jsx'
import Wizard from './pages/Wizard.jsx'
import Tasks from './pages/Tasks.jsx'
import TaskCreate from './pages/TaskCreate.jsx'
import TaskEdit from './pages/TaskEdit.jsx'
import TaskDetail from './pages/TaskDetail.jsx'
import Templates from './pages/Templates.jsx'
import Demands from './pages/Demands.jsx'

const { Sider, Header, Content } = Layout

const items = [
  { key: '/systems', icon: <CloudServerOutlined />, label: '目标系统' },
  { key: '/wizard', icon: <ApiOutlined />, label: '接入向导' },
  { key: '/tasks', icon: <ScheduleOutlined />, label: '任务管理' },
  { key: '/templates', icon: <AppstoreOutlined />, label: '任务模板' },
  { key: '/demands', icon: <BulbOutlined />, label: '需求中心' }
]

function Shell({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const selected = '/' + location.pathname.split('/')[1]
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={200}>
        <div style={{ color: '#fff', padding: '20px 16px', fontSize: 16, fontWeight: 600 }}>
          newPRAsystem
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            alignItems: 'center',
            fontSize: 15,
            fontWeight: 500
          }}
        >
          网页解析式自动化任务平台
        </Header>
        <Content style={{ padding: 24, background: '#f5f5f5' }}>{children}</Content>
      </Layout>
    </Layout>
  )
}

export default function App() {
  return (
    <HashRouter>
      <Shell>
        <Routes>
          <Route path="/systems" element={<Systems />} />
          <Route path="/wizard" element={<Wizard />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/tasks/new" element={<TaskCreate />} />
          <Route path="/tasks/:id/edit" element={<TaskEdit />} />
          <Route path="/tasks/:id" element={<TaskDetail />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/demands" element={<Demands />} />
          <Route path="*" element={<Navigate to="/tasks" replace />} />
        </Routes>
      </Shell>
    </HashRouter>
  )
}
