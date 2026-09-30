import React, { useEffect, useRef, useState } from 'react'
import {
  Card, Descriptions, Table, Tag, Button, Drawer, Timeline,
  Spin, Empty, message, Space, Typography, Modal, Input, Dropdown
} from 'antd'
import {
  PlayCircleOutlined, DownloadOutlined, ReloadOutlined,
  EditOutlined, SyncOutlined, ExportOutlined, SaveOutlined
} from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { api } from '../api.js'

const STATUS_TAG = {
  succeeded: <Tag color="success">成功</Tag>,
  failed: <Tag color="error">失败</Tag>,
  running: <Tag color="processing">运行中</Tag>
}

export default function TaskDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState(null)
  const [runs, setRuns] = useState([])
  const [detail, setDetail] = useState(null)   // Drawer 中的运行详情
  const [loading, setLoading] = useState(false)
  const [tplOpen, setTplOpen] = useState(false)
  const [tplName, setTplName] = useState('')
  const [tplDesc, setTplDesc] = useState('')

  const saveTemplate = async () => {
    if (!tplName.trim()) return message.warning('请填写模板名称')
    await api.post('/api/templates', {
      task_id: task.id, name: tplName.trim(), description: tplDesc.trim(),
    })
    message.success('已保存为模板，可在「任务模板」页查看')
    setTplOpen(false)
    setTplName(''); setTplDesc('')
  }
  const timerRef = useRef(null)

  const load = () => {
    setLoading(true)
    Promise.all([api.get(`/api/tasks/${id}`), api.get(`/api/runs?task_id=${id}`)])
      .then(([t, r]) => { setTask(t); setRuns(r) })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => {
    load()
    // SSE 实时推送：本任务有任何 run 事件（running/retrying/succeeded/failed）立即刷新
    const es = new EventSource('/api/events')
    es.addEventListener('run', (e) => {
      try {
        const d = JSON.parse(e.data)
        if (d.task_id === Number(id)) load()
      } catch { /* 忽略坏事件 */ }
    })
    return () => { es.close(); clearInterval(timerRef.current) }
  }, [])

  // 轮询兜底：SSE 断连或事件丢失时，存在运行中记录仍周期刷新
  useEffect(() => {
    clearInterval(timerRef.current)
    if (runs.some((r) => r.status === 'running')) {
      timerRef.current = setInterval(load, 8000)
    }
  }, [runs])

  const runNow = async () => {
    try {
      await api.post(`/api/tasks/${id}/run`)
      message.success('已触发运行')
      setTimeout(load, 2000)
    } catch (e) { message.error(e.message) }
  }

  const openDetail = (r) => setDetail(r)
  const refreshDetail = async () => {
    const r = await api.get(`/api/runs/${detail.id}`)
    setDetail(r)
  }

  if (loading && !task) return <Card><Spin /></Card>
  if (!task) return <Card><Empty description="任务不存在" /></Card>

  const columns = [
    { title: '运行 ID', dataIndex: 'id', width: 90 },
    { title: '状态', dataIndex: 'status', width: 100, render: (s) => STATUS_TAG[s] || <Tag>{s}</Tag> },
    {
      title: '触发方式', dataIndex: 'trigger', width: 100,
      render: (t) => {
        const m = { scheduled: ['blue', '定时'], manual: ['orange', '手动'], webhook: ['purple', 'Webhook'] }
        const [color, label] = m[t] || ['default', t]
        return <Tag color={color}>{label}</Tag>
      }
    },
    {
      title: '开始时间', dataIndex: 'started_at', width: 170,
      render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm:ss')
    },
    {
      title: '结束时间', dataIndex: 'finished_at', width: 170,
      render: (v) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-')
    },
    {
      title: '产物', dataIndex: 'artifacts', ellipsis: true,
      render: (arts, r) =>
        arts?.length ? (
          <Space size={8} wrap>
            {arts.map((a) => (
              <Button
                key={a} size="small" type="link" icon={<DownloadOutlined />}
                href={`/api/runs/${r.id}/files/${a.split('/').map(encodeURIComponent).join('/')}`}
                target="_blank"
              >
                {a.split('/').pop()}
              </Button>
            ))}
          </Space>
        ) : (
          '-'
        )
    },
    {
      title: '操作', width: 110,
      render: (_, r) => (
        <Button size="small" onClick={() => openDetail(r)}>
          执行详情
        </Button>
      )
    }
  ]

  const configEntries = Object.entries(task.config || {})

  return (
    <Card
      title={`任务 #${task.id} · ${task.name}`}
      extra={
        <Space>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={runNow}>
            立即运行
          </Button>
          <Button icon={<EditOutlined />} onClick={() => navigate(`/tasks/${task.id}/edit`)}>
            编辑配置
          </Button>
          <Button icon={<SyncOutlined />} onClick={() => navigate(`/wizard?profileId=${task.profile_id}`)}>
            更新页面档案
          </Button>
          <Dropdown
            menu={{
              items: [
                { key: 'plain', label: '导出任务包（不含密码，交付时自行填写）' },
                { key: 'embed', label: '导出任务包（预填密码，仅内部交付）' },
              ],
              onClick: ({ key }) => window.open(
                `/api/tasks/${task.id}/export${key === 'embed' ? '?embed_credentials=true' : ''}`,
                '_blank'
              ),
            }}
          >
            <Button icon={<ExportOutlined />}>导出任务包</Button>
          </Dropdown>
          <Button icon={<SaveOutlined />} onClick={() => setTplOpen(true)}>
            保存为模板
          </Button>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      }
    >
      <Descriptions bordered size="small" column={2} style={{ marginBottom: 24 }}>
        <Descriptions.Item label="目标页面" span={2}>
          {task.profile_url || '-'}
          <Tag style={{ marginLeft: 8 }}>档案 v{task.profile_version || 1}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="主动作">{task.action}</Descriptions.Item>
        <Descriptions.Item label="前置动作">
          {task.pre_actions?.length ? task.pre_actions.join(' → ') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="调度" span={2}>
          {task.schedule?.enabled ? `cron: ${task.schedule.cron}` : '手动运行'}
        </Descriptions.Item>
        <Descriptions.Item label="业务条件" span={2}>
          {configEntries.length
            ? configEntries.map(([k, v]) => (
              <Tag key={k}>
                {k} = {Array.isArray(v) ? v.join('、') : typeof v === 'object' ? v.preset : String(v ?? '')}
              </Tag>
            ))
            : '无筛选条件'}
        </Descriptions.Item>
        <Descriptions.Item label="交付方式">
          {task.delivery?.type === 'email' ? `邮件 → ${(task.delivery.to || []).join('、')}` : '仅平台留存'}
        </Descriptions.Item>
        <Descriptions.Item label="失败重试">
          {task.retry_count ? `自动重试 ${task.retry_count} 次` : '不重试'}
        </Descriptions.Item>
        <Descriptions.Item label="外部触发 Webhook" span={2}>
          <Typography.Text copyable code style={{ fontSize: 12 }}>
            POST {window.location.origin}/api/trigger/{task.trigger_token}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="上次运行">
          {task.last_run_at ? dayjs(task.last_run_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
        </Descriptions.Item>
      </Descriptions>

      <h4>运行历史</h4>
      <Table
        rowKey="id" size="small" pagination={{ pageSize: 10 }}
        columns={columns} dataSource={runs}
        locale={{ emptyText: '暂无运行记录' }}
      />

      <Drawer
        title={`运行 #${detail?.id} 执行详情`}
        width={640} open={!!detail}
        onClose={() => setDetail(null)}
        extra={<Button size="small" icon={<ReloadOutlined />} onClick={refreshDetail}>刷新</Button>}
      >
        {detail && (
          <>
            <Descriptions bordered size="small" column={1} style={{ marginBottom: 24 }}>
              <Descriptions.Item label="状态">
                {STATUS_TAG[detail.status] || detail.status}
                {detail.error ? <div style={{ color: '#cf1322', marginTop: 4 }}>{detail.error}</div> : null}
              </Descriptions.Item>
            </Descriptions>
            <h4>执行步骤</h4>
            <Timeline
              items={(detail.steps || []).map((s) => ({
                children: (
                  <span>
                    <Tag style={{ marginRight: 8 }}>{s.time}</Tag>
                    {s.msg}
                  </span>
                )
              }))}
            />
            {detail.status === 'running' && <Spin tip="运行中，稍后点击右上角刷新…" />}
          </>
        )}
      </Drawer>

      <Modal
        title="保存为任务模板" open={tplOpen} onOk={saveTemplate}
        onCancel={() => setTplOpen(false)} okText="保存"
      >
        <p style={{ color: '#888' }}>
          模板将抽取本任务的业务条件、前置动作与主动作（不含目标页面与账号），
          之后可基于模板快速创建同类型任务。
        </p>
        <Input
          placeholder="模板名称，如：华东区周报导出" value={tplName}
          onChange={(e) => setTplName(e.target.value)} style={{ marginBottom: 12 }}
        />
        <Input.TextArea
          rows={2} placeholder="模板说明（可选）" value={tplDesc}
          onChange={(e) => setTplDesc(e.target.value)}
        />
      </Modal>
    </Card>
  )
}
