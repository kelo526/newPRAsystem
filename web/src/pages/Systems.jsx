import React, { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, Popconfirm, message, Tag, Space
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, ArrowRightOutlined, EditOutlined, ImportOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

export default function Systems() {
  const [systems, setSystems] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null) // null=新建；对象=编辑
  const [form] = Form.useForm()
  const navigate = useNavigate()

  const load = () => api.get('/api/systems').then(setSystems).catch((e) => message.error(e.message))
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setOpen(true)
  }

  const openEdit = (record) => {
    setEditing(record)
    form.setFieldsValue({
      name: record.name, login_url: record.login_url,
      username: record.username, password: '',
      username_selector: record.username_selector,
      password_selector: record.password_selector,
      pre_clicks_text: (record.pre_clicks || []).join('\n'),
    })
    setOpen(true)
  }

  const onSubmit = async () => {
    const values = await form.validateFields()
    const pre_clicks = (values.pre_clicks_text || '')
      .split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
    const body = { ...values, pre_clicks }
    delete body.pre_clicks_text
    try {
      if (editing) {
        if (!body.password) delete body.password // 密码留空 = 不修改
        await api.put(`/api/systems/${editing.id}`, body)
        message.success('系统配置已更新')
      } else {
        await api.post('/api/systems', body)
        message.success('目标系统已创建（密码已加密存储）')
      }
      setOpen(false)
      load()
    } catch (e) {
      message.error(e.message)
    }
  }

  const onDelete = async (id) => {
    try {
      await api.del(`/api/systems/${id}`)
      message.success('已删除')
      load()
    } catch (e) {
      message.error(e.message)
    }
  }

  // ---- 人工会话导入（验证码类系统的插件辅助先行版）----
  const [sessSystem, setSessSystem] = useState(null) // 正在导入会话的系统
  const [sessText, setSessText] = useState('')

  const importSession = async () => {
    let state
    try {
      state = JSON.parse(sessText)
    } catch {
      return message.error('JSON 解析失败，请粘贴完整的 Playwright storage_state 内容')
    }
    try {
      const r = await api.put(`/api/systems/${sessSystem.id}/session`, { state })
      message.success(`会话已导入，解析与任务运行将免登录直达（${r.saved}）`)
      setSessSystem(null)
      setSessText('')
    } catch (e) {
      message.error(e.message)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '系统名称', dataIndex: 'name' },
    { title: '登录页', dataIndex: 'login_url', ellipsis: true },
    { title: '账号', dataIndex: 'username', width: 120 },
    {
      title: '操作', width: 340,
      render: (_, record) => (
        <Space>
          <Button
            type="link" size="small" icon={<ArrowRightOutlined />}
            onClick={() => navigate(`/wizard?systemId=${record.id}`)}
          >
            接入解析
          </Button>
          <Button
            type="link" size="small" icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Button
            type="link" size="small" icon={<ImportOutlined />}
            onClick={() => { setSessSystem(record); setSessText('') }}
          >
            导入会话
          </Button>
          <Popconfirm title="确认删除该系统？" onConfirm={() => onDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <Card
      title="目标系统"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建系统
        </Button>
      }
    >
      <Table
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={systems}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: '暂无目标系统，点击右上角新建' }}
      />
      <Modal
        title={editing ? `编辑系统：${editing.name}` : '新建目标系统'}
        open={open}
        onOk={onSubmit}
        onCancel={() => setOpen(false)}
        okText={editing ? '保存' : '创建'}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="系统名称" rules={[{ required: true }]}>
            <Input placeholder="如：订单经营管理系统" />
          </Form.Item>
          <Form.Item name="login_url" label="登录页 URL" rules={[{ required: true }]}>
            <Input placeholder="http://…/login" />
          </Form.Item>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input placeholder="登录账号" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={editing ? [] : [{ required: true }]}
            extra={editing ? '留空表示不修改' : undefined}
          >
            <Input.Password placeholder={editing ? '留空保持不变' : '将加密存储'} />
          </Form.Item>
          <Form.Item
            name="username_selector"
            label="用户名输入框选择器（可选，默认按中文占位符匹配）"
          >
            <Input placeholder="如 input[name='username']" />
          </Form.Item>
          <Form.Item name="password_selector" label="密码输入框选择器（可选）">
            <Input placeholder="如 input[name='password']" />
          </Form.Item>
          <Form.Item
            name="pre_clicks_text"
            label="登录前置点击（两步式门户，每行一个）"
            extra="部分系统登录前需先点击门户页入口（如「进入系统」），此处填写点击目标（选择器或 text=按钮文本），将依次点击后再自动登录"
          >
            <Input.TextArea
              rows={2}
              placeholder={"text=进入系统\n#start-btn"}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`导入登录会话：${sessSystem?.name || ''}`}
        open={!!sessSystem}
        onOk={importSession}
        onCancel={() => { setSessSystem(null); setSessText('') }}
        okText="导入"
        width={640}
      >
        <p style={{ color: '#888', marginBottom: 8 }}>
          适用于含验证码等无法自动登录的系统：在本地浏览器（或配套插件）完成登录后，
          将 Playwright storage_state JSON（含 cookies / origins）粘贴到此处。
          导入后解析与任务运行将直接复用该会话，免自动登录。
        </p>
        <Input.TextArea
          rows={10}
          placeholder='{"cookies": [...], "origins": [...]}'
          value={sessText}
          onChange={(e) => setSessText(e.target.value)}
        />
      </Modal>
    </Card>
  )
}
