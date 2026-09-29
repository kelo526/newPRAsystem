import React, { useEffect, useRef, useState } from 'react'
import {
  Card, Steps, Form, Select, Input, Button, Spin, Alert, Table, Tag, Switch,
  message, Space, Result
} from 'antd'
import { CheckCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'

const KIND_LABEL = {
  query: '查询', reset: '重置', export: '导出', upload: '上传',
  submit: '提交', other: '其他'
}

export default function Wizard() {
  const [step, setStep] = useState(0)
  const [systems, setSystems] = useState([])
  const [form] = Form.useForm()
  const [req, setReq] = useState(null)
  const [profile, setProfile] = useState(null)
  const [fields, setFields] = useState([])
  const [actions, setActions] = useState([])
  const timerRef = useRef(null)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const updateProfileId = Number(params.get('profileId')) || null

  useEffect(() => {
    if (updateProfileId) {
      // 更新模式：拉取档案信息用于展示
      api.get(`/api/profiles/${updateProfileId}`)
        .then((p) => { setProfile(p); setFields(p.fields || []); setActions(p.actions || []) })
        .catch((e) => message.error(e.message))
    } else {
      api.get('/api/systems').then(setSystems).catch((e) => message.error(e.message))
      const sysId = params.get('systemId')
      if (sysId) form.setFieldValue('system_id', Number(sysId))
    }
    return () => clearTimeout(timerRef.current)
  }, [])

  // 提交解析（新建模式：表单；更新模式：reparse 已有档案）
  const startParse = async () => {
    try {
      if (updateProfileId) {
        const r = await api.post(`/api/profiles/${updateProfileId}/reparse`)
        setReq(r)
        setStep(1)
        poll(r.id)
        return
      }
      const values = await form.validateFields()
      const r = await api.post('/api/parse-requests', values)
      setReq(r)
      setStep(1)
      poll(r.id)
    } catch (e) {
      if (e?.errorFields) return // 表单校验错误
      message.error(e.message)
    }
  }

  // 轮询解析状态
  const poll = (reqId) => {
    timerRef.current = setTimeout(async () => {
      try {
        const r = await api.get(`/api/parse-requests/${reqId}`)
        if (r.status === 'running') {
          poll(reqId)
          return
        }
        if (r.status === 'failed') {
          setReq(r)
          setStep(1)
          return
        }
        const prof = await api.get(`/api/profiles/${r.profile_id}`)
        prof.fields.forEach((f) => (f.included = f.included !== false))
        prof.actions.forEach((a) => (a.included = a.included !== false))
        setProfile(prof)
        setFields(prof.fields)
        setActions(prof.actions)
        setStep(2)
        message.success(`解析完成：${prof.fields.length} 个字段、${prof.actions.length} 个动作`)
      } catch (e) {
        message.error(e.message)
      }
    }, 2500)
  }

  // 字段确认提交
  const confirm = async () => {
    try {
      await api.put(`/api/profiles/${profile.id}/confirm`, { fields, actions })
      message.success('档案已确认，可以创建任务')
    } catch (e) {
      message.error(e.message)
    }
  }

  const fieldColumns = [
    {
      title: '纳入', dataIndex: 'included', width: 70,
      render: (_, record, i) => (
        <Switch
          size="small"
          checked={record.included}
          onChange={(v) => {
            const next = [...fields]; next[i].included = v; setFields(next)
          }}
        />
      )
    },
    {
      title: '业务名称', dataIndex: 'semantic_name', width: 200,
      render: (_, record, i) => (
        <Space size={6}>
          <Input
            size="small" value={record.semantic_name}
            onChange={(e) => {
              const next = [...fields]; next[i].semantic_name = e.target.value; setFields(next)
            }}
          />
          {record.is_new && <Tag color="orange">新增</Tag>}
        </Space>
      )
    },
    { title: '类型', dataIndex: 'type', width: 110, render: (t) => <Tag>{t}</Tag> },
    {
      title: '网页标签', dataIndex: 'label', width: 120, ellipsis: true
    },
    {
      title: '选项', dataIndex: 'options', ellipsis: true,
      render: (opts) =>
        opts?.length ? (
          <Space size={4} wrap>
            {opts.slice(0, 6).map((o) => (
              <Tag key={o} style={{ fontSize: 12 }}>{o}</Tag>
            ))}
            {opts.length > 6 && <Tag>+{opts.length - 6}</Tag>}
          </Space>
        ) : (
          '-'
        )
    }
  ]

  const actionColumns = [
    {
      title: '纳入', dataIndex: 'included', width: 70,
      render: (_, record, i) => (
        <Switch
          size="small"
          checked={record.included}
          onChange={(v) => {
            const next = [...actions]; next[i].included = v; setActions(next)
          }}
        />
      )
    },
    {
      title: '动作名称', dataIndex: 'semantic_name', width: 180,
      render: (_, record, i) => (
        <Input
          size="small" value={record.semantic_name}
          onChange={(e) => {
            const next = [...actions]; next[i].semantic_name = e.target.value; setActions(next)
          }}
        />
      )
    },
    { title: '类型', dataIndex: 'kind', width: 100, render: (k) => <Tag color="blue">{KIND_LABEL[k] || k}</Tag> }
  ]

  return (
    <Card title="接入向导：解析目标页面，确认业务字段">
      <Steps
        current={step}
        items={
          updateProfileId
            ? [{ title: '更新档案' }, { title: '重新解析' }, { title: '差异确认' }]
            : [{ title: '选择系统与页面' }, { title: '自动解析' }, { title: '字段确认' }]
        }
        style={{ marginBottom: 24 }}
      />

      {step === 0 && updateProfileId && profile && (
        <div style={{ maxWidth: 560 }}>
          <Alert
            type="info" showIcon style={{ marginBottom: 16 }}
            message={`更新页面档案 #${profile.id}（当前 v${profile.version}）`}
            description={`目标页面：${profile.target_url}。重新解析后，已确认字段的业务名称与纳入标记会保留，网页上新增的字段将标记为「新增」并默认不纳入，需在下一步确认。`}
          />
          <Space>
            <Button type="primary" onClick={startParse}>
              开始重新解析
            </Button>
            <Button onClick={() => navigate('/tasks')}>返回</Button>
          </Space>
        </div>
      )}

      {step === 0 && !updateProfileId && (
        <Form form={form} layout="vertical" style={{ maxWidth: 560 }}>
          <Form.Item name="system_id" label="目标系统" rules={[{ required: true, message: '请选择系统' }]}>
            <Select
              placeholder="选择已登记的目标系统"
              options={systems.map((s) => ({ label: `${s.name}（${s.username}）`, value: s.id }))}
            />
          </Form.Item>
          <Form.Item
            name="target_url" label="报表页面 URL"
            rules={[{ required: true, message: '请输入目标页面 URL' }]}
          >
            <Input placeholder="http://…/report（登录后可见的业务页面）" />
          </Form.Item>
          <Button type="primary" onClick={startParse}>
            开始解析
          </Button>
        </Form>
      )}

      {step === 1 && (
        req?.status === 'failed' ? (
          <Result
            status="error"
            title="解析失败"
            subTitle={req.error || '未知错误'}
            extra={[
              <Button key="retry" icon={<ReloadOutlined />} onClick={() => setStep(0)}>
                返回重试
              </Button>
            ]}
          />
        ) : (
          <div style={{ padding: '48px 0', textAlign: 'center' }}>
            <Spin size="large" />
            <p style={{ marginTop: 16, color: '#888' }}>
              正在打开目标页面并解析业务字段（含下拉选项抓取），通常需要 20~60 秒…
            </p>
          </div>
        )
      )}

      {step === 2 && profile && (
        <>
          {profile.meta?.last_reparse ? (
            <Alert
              style={{ marginBottom: 16 }}
              type="warning" showIcon
              message={`档案已更新到 v${profile.version}`}
              description={
                `新增字段：${profile.meta.last_reparse.added?.join('、') || '无'}；` +
                `移除字段：${profile.meta.last_reparse.removed?.join('、') || '无'}。` +
                `新增字段默认不纳入，勾选「纳入」开关后才会出现在任务配置中。`
              }
            />
          ) : (
            <Alert
              style={{ marginBottom: 16 }}
              type="info" showIcon
              message={`页面档案 #${profile.id} · ${profile.target_url}`}
              description="检查并修正字段业务名称，勾选要纳入任务配置的字段与动作，然后确认档案。"
            />
          )}
          <h4>可配置字段（{fields.length}）</h4>
          <Table
            rowKey="key" size="small" pagination={false}
            columns={fieldColumns} dataSource={fields}
            style={{ marginBottom: 24 }}
          />
          <h4>可执行动作（{actions.length}）</h4>
          <Table
            rowKey="key" size="small" pagination={false}
            columns={actionColumns} dataSource={actions}
            style={{ marginBottom: 24 }}
          />
          <Space>
            <Button icon={<CheckCircleOutlined />} onClick={confirm}>
              确认档案
            </Button>
            <Button
              type="primary"
              onClick={() => navigate(`/tasks/new?profileId=${profile.id}`)}
            >
              基于此档案创建任务 →
            </Button>
          </Space>
        </>
      )}
    </Card>
  )
}
