import React from 'react'
import { Card } from 'antd'
import TaskForm from './TaskForm.jsx'

export default function TaskCreate() {
  return (
    <Card title="新建自动化任务">
      <TaskForm />
    </Card>
  )
}
