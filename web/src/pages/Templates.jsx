import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Tag, Modal, Input, message, Popconfirm, Empty } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { api } from '../api.js'

export default function Templates() {
  const navigate = useNavigate()
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(false)

  const load = () => {
    setLoading(true)
    api.get('/api/templates')
      .then(setList)
      .catch(() => message.error('加载模板失败'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const columns = [
    { title: '模板名称', dataIndex: 'name' },
    {
      title: '包含配置', dataIndex: 'payload',
      render: (p) => (
        <span>
          <Tag color="blue">{p?.action || '-'}</Tag>
          {Object.keys(p?.config || {}).length} 个条件
          {(p?.pre_actions || []).length > 0 && `，前置：${p.pre_actions.join('、')}`}
        </span>
      )
    },
    { title: '说明', dataIndex: 'description', ellipsis: true },
    {
      title: '创建时间', dataIndex: 'created_at', width: 160,
      render: (t) => dayjs(t).format('YYYY-MM-DD HH:mm')
    },
    {
      title: '操作', width: 200,
      render: (_, tpl) => (
        <span>
          <Button
            size="small" type="primary" icon={<PlusOutlined />}
            onClick={() => navigate(`/tasks/new?template=${tpl.id}`)}
            style={{ marginRight: 8 }}
          >
            创建任务
          </Button>
          <Popconfirm title="删除该模板？" onConfirm={() => {
            api.delete(`/api/templates/${tpl.id}`).then(load)
          }}>
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </span>
      )
    }
  ]

  return (
    <Card title="任务模板（沉淀复用）">
      <p style={{ color: '#888', marginBottom: 16 }}>
        模板保存任务的业务条件与动作（不含目标页面绑定和账号）。
        在任务详情页点「保存为模板」沉淀，此处可基于模板快速创建同类型任务——
        选择目标页面档案后条件自动预填。
      </p>
      <Table
        rowKey="id" size="middle" loading={loading}
        columns={columns} dataSource={list}
        locale={{ emptyText: <Empty description="暂无模板：到任务详情页「保存为模板」" /> }}
      />
    </Card>
  )
}
