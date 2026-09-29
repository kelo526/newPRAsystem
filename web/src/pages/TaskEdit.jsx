import React from 'react'
import { Card } from 'antd'
import { useParams } from 'react-router-dom'
import TaskForm from './TaskForm.jsx'

export default function TaskEdit() {
  const { id } = useParams()
  return (
    <Card title={`编辑任务 #${id}（调整业务配置，无需重建流程）`}>
      <TaskForm initial={{ id: Number(id) }} />
    </Card>
  )
}
