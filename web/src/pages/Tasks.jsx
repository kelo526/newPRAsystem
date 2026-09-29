import React, { useEffect, useState } from 'react'
import {
  Card, Table, Button, Popconfirm, message, Tag, Space, Tooltip
} from 'antd'
import {
  PlayCircleOutlined, DeleteOutlined, EyeOutlined, PlusOutlined,
  CopyOutlined, EditOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { api } from '../api.js'

const STATUS = {
  succeeded: <Tag color="success">成功</Tag>,
  failed: <Tag color="error">失败</Tag>,
  running: <Tag color="processing">运行中</Tag>
}

export default function Tasks() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    api.get('/api/tasks')
      .then(setTasks)
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => {
    load()
    // SSE 实时推送：任意任务 run 状态变化（running/成功/失败）即刷新列表
    const es = new EventSource('/api/events')
    es.addEventListener('run', () => load())
    return () => es.close()
  }, [])

  const runNow = async (id) => {
    try {
      await api.post(`/api/tasks/${id}/run`)
      message.success('已触发运行')
      setTimeout(load, 2000) // SSE 兜底
    } catch (e) { message.error(e.message) }
  }

  const remove = async (id) => {
    try {
      await api.del(`/api/tasks/${id}`)
      message.success('已删除')
      load()
    } catch (e) { message.error(e.message) }
  }

  const duplicate = async (id) => {
    try {
      await api.post(`/api/tasks/${id}/duplicate`)
      message.success('已创建副本（默认停用调度），可编辑调整条件后启用')
      load()
    } catch (e) { message.error(e.message) }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '任务名称', dataIndex: 'name', render: (v, r) => (
      <Button type="link" style={{ padding: 0 }} onClick={() => navigate(`/tasks/${r.id}`)}>{v}</Button>
    )},
    { title: '目标页面', dataIndex: 'profile_url', ellipsis: true },
    {
      title: '调度', width: 120,
      render: (_, r) =>
        r.schedule?.enabled && r.schedule?.cron ? (
          <Tooltip title={`下次运行：${r.schedule_next ? dayjs(r.schedule_next).format('YYYY-MM-DD HH:mm') : '-'}`}>
            <Tag color="blue">{r.schedule.cron}</Tag>
          </Tooltip>
        ) : (
          <Tag>手动</Tag>
        )
    },
    {
      title: '启用', dataIndex: 'enabled', width: 70,
      render: (v) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>)
    },
    {
      title: '上次运行', dataIndex: 'last_run_at', width: 160,
      render: (v) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-')
    },
    {
      title: '操作', width: 230,
      render: (_, r) => (
        <Space>
          <Tooltip title="立即运行">
            <Button size="small" type="primary" ghost icon={<PlayCircleOutlined />} onClick={() => runNow(r.id)} />
          </Tooltip>
          <Tooltip title="编辑配置">
            <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/tasks/${r.id}/edit`)} />
          </Tooltip>
          <Tooltip title="创建副本">
            <Button size="small" icon={<CopyOutlined />} onClick={() => duplicate(r.id)} />
          </Tooltip>
          <Tooltip title="运行历史">
            <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/tasks/${r.id}`)} />
          </Tooltip>
          <Popconfirm title="确认删除任务及其运行记录？" onConfirm={() => remove(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <Card
      title="任务管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks/new')}>
          新建任务
        </Button>
      }
    >
      <Table
        rowKey="id" size="middle" loading={loading}
        columns={columns} dataSource={tasks}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: '暂无任务。通过「接入向导」解析页面并创建任务' }}
      />
    </Card>
  )
}
