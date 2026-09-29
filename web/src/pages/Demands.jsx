import React, { useEffect, useState } from 'react'
import {
  Card, Table, Button, Tag, Modal, Input, Select, message, Popconfirm, Form
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../api.js'

const STATUS = {
  pending: { text: '待评估', color: 'orange' },
  accepted: { text: '已受理', color: 'blue' },
  done: { text: '已完成', color: 'green' },
  rejected: { text: '不适用', color: 'default' }
}

export default function Demands() {
  const [list, setList] = useState([])
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()
  const [noteFor, setNoteFor] = useState(null)
  const [note, setNote] = useState('')

  const load = () => {
    api.get('/api/demands').then(setList).catch(() => message.error('加载失败'))
  }
  useEffect(load, [])

  const submit = async () => {
    const v = await form.validateFields()
    await api.post('/api/demands', v)
    message.success('需求已提交，等待评估')
    setOpen(false)
    form.resetFields()
    load()
  }

  const setStatus = (id, status) => {
    api.put(`/api/demands/${id}`, { status }).then(() => {
      message.success('状态已更新')
      load()
    })
  }

  const columns = [
    { title: '需求标题', dataIndex: 'title' },
    {
      title: '提交人', dataIndex: 'submitter', width: 110,
      render: (s) => s || '匿名'
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (s) => <Tag color={STATUS[s]?.color}>{STATUS[s]?.text || s}</Tag>
    },
    {
      title: '说明', dataIndex: 'description', ellipsis: true
    },
    {
      title: '跟进备注', dataIndex: 'note', ellipsis: true,
      render: (n, d) => (
        <a onClick={() => { setNoteFor(d); setNote(n || '') }}>{n || '（点击填写）'}</a>
      )
    },
    {
      title: '提交时间', dataIndex: 'created_at', width: 150,
      render: (t) => dayjs(t).format('MM-DD HH:mm')
    },
    {
      title: '操作', width: 200,
      render: (_, d) => (
        <span>
          {d.status === 'pending' && (
            <>
              <Button size="small" type="primary" style={{ marginRight: 6 }}
                onClick={() => setStatus(d.id, 'accepted')}>受理</Button>
              <Button size="small" style={{ marginRight: 6 }}
                onClick={() => setStatus(d.id, 'rejected')}>不适用</Button>
            </>
          )}
          {d.status === 'accepted' && (
            <Button size="small" type="primary" style={{ marginRight: 6 }}
              onClick={() => setStatus(d.id, 'done')}>标记完成</Button>
          )}
          <Popconfirm title="删除该需求？" onConfirm={() => {
            api.delete(`/api/demands/${d.id}`).then(load)
          }}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </span>
      )
    }
  ]

  return (
    <Card
      title="需求中心"
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
        提交自动化需求
      </Button>}
    >
      <p style={{ color: '#888', marginBottom: 16 }}>
        业务人员在此提交希望自动化的网页操作需求（如"每周一导出 XX 报表发给我"），
        平台管理员评估后在任务管理中落地，状态全程可跟踪。
      </p>
      <Table rowKey="id" size="middle" columns={columns} dataSource={list} />

      <Modal title="提交自动化需求" open={open} onOk={submit} onCancel={() => setOpen(false)} okText="提交">
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="需求标题" rules={[{ required: true, message: '请填写标题' }]}>
            <Input placeholder="如：每周一 9 点导出华东区订单周报并邮件发送" />
          </Form.Item>
          <Form.Item name="description" label="详细说明">
            <Input.TextArea rows={4} placeholder="目标系统、页面、筛选条件、频率、产物去向等" />
          </Form.Item>
          <Form.Item name="submitter" label="提交人">
            <Input placeholder="姓名或工号" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="跟进备注" open={!!noteFor} okText="保存"
        onOk={() => {
          api.put(`/api/demands/${noteFor.id}`, { note }).then(() => {
            setNoteFor(null); load()
          })
        }}
        onCancel={() => setNoteFor(null)}
      >
        <Input.TextArea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </Modal>
    </Card>
  )
}
