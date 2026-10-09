import React, { useEffect, useMemo, useState } from 'react'
import {
  Form, Input, Select, Button, Radio, Space, DatePicker, Switch,
  Divider, Tag, message, InputNumber, Typography, AutoComplete
} from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import { api } from '../api.js'

const PRESETS = [
  { label: '最近 7 天', value: 'last_7_days' },
  { label: '最近 30 天', value: 'last_30_days' },
  { label: '上周（周一~周日）', value: 'last_week' },
  { label: '上月', value: 'last_month' },
  { label: '昨天', value: 'yesterday' },
  { label: '今天', value: 'today' },
  { label: '本月至今', value: 'month_to_date' },
  { label: '自定义日期', value: '__custom' }
]

const CRON_PRESETS = [
  { label: '每天 09:00', value: '0 9 * * *' },
  { label: '每周一 09:00', value: '0 9 * * 1' },
  { label: '每月 1 日 09:00', value: '0 9 1 * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '自定义', value: 'custom' }
]

/** 动态字段控件：由页面档案字段类型驱动渲染 */
function FieldControl({ field, value, onChange }) {
  if (field.type === 'date_range') {
    const preset = Array.isArray(value) ? '__custom' : value?.preset || 'last_7_days'
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Select
          style={{ width: 240 }}
          options={PRESETS}
          value={preset}
          onChange={(v) =>
            onChange(v === '__custom' ? [dayjs().format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')] : { preset: v })
          }
        />
        {preset === '__custom' && (
          <DatePicker.RangePicker
            value={Array.isArray(value) ? value.map((d) => dayjs(d)) : undefined}
            onChange={(dates) =>
              onChange(dates ? dates.map((d) => d.format('YYYY-MM-DD')) : undefined)
            }
          />
        )}
      </Space>
    )
  }
  if (field.type === 'select') {
    // AutoComplete：可选解析出的选项，也允许手动输入（如树形下拉中未展开的子节点）
    return (
      <AutoComplete
        style={{ width: 240 }} allowClear
        placeholder={`选择或输入${field.semantic_name}`}
        options={field.options?.map((o) => ({ label: o, value: o })) || []}
        filterOption={(input, option) =>
          (option?.value || '').toLowerCase().includes(input.toLowerCase())
        }
        value={value}
        onChange={onChange}
      />
    )
  }
  if (field.type === 'multi_select') {
    return (
      <Select
        mode="multiple" style={{ minWidth: 240 }} allowClear
        placeholder={`选择${field.semantic_name}`}
        options={field.options?.map((o) => ({ label: o, value: o })) || []}
        value={value}
        onChange={onChange}
      />
    )
  }
  if (field.type === 'radio') {
    return (
      <Radio.Group
        options={field.options?.map((o) => ({ label: o, value: o })) || []}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }
  return (
    <Input
      style={{ width: 240 }} allowClear placeholder={field.placeholder || ''}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

/**
 * 任务表单（新建 / 编辑共用）
 * - initial 传入已有任务（编辑模式）：回填配置并锁定档案选择
 * - initial 为 null（新建模式）：选择档案
 */
export default function TaskForm({ initial = null, onSaved }) {
  const navigate = useNavigate()
  const [profileList, setProfileList] = useState([])
  const [profile, setProfile] = useState(null)
  const [name, setName] = useState('')
  const [config, setConfig] = useState({})
  const [action, setAction] = useState(null)
  const [preActions, setPreActions] = useState([])
  const [cronMode, setCronMode] = useState('0 9 * * 1')
  const [cronText, setCronText] = useState('')
  const [cronEnabled, setCronEnabled] = useState(true)
  const [deliveryType, setDeliveryType] = useState('none')
  const [deliveryTo, setDeliveryTo] = useState('')
  const [feishuWebhook, setFeishuWebhook] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [exportTimeout, setExportTimeout] = useState(180)
  const [noProfiles, setNoProfiles] = useState(false)
  const [searchParams] = useSearchParams()

  useEffect(() => {
    api.get('/api/profiles')
      .then((list) => {
        if (initial) return // 编辑模式：档案由回填逻辑提供
        setProfileList(list)
        setNoProfiles(!list.some((p) => p.confirmed))
        const target = list.find((p) => p.confirmed) || null
        if (target) setProfile(target)
      })
      .catch(() => {})
  }, [])

  // 模板预填（从任务模板页进入）：业务条件/动作自动带入
  useEffect(() => {
    const tid = searchParams.get('template')
    if (!tid || initial) return
    api.get('/api/templates')
      .then((list) => {
        const tpl = list.find((t) => t.id === Number(tid))
        if (!tpl) return
        setConfig(tpl.payload.config || {})
        setPreActions(tpl.payload.pre_actions || [])
        setAction(tpl.payload.action || '')
        setName(`${tpl.name}-${dayjs().format('MMDD-HHmm')}`)
        message.info(`已按模板「${tpl.name}」预填，请选择页面档案后核对`)
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 编辑模式回填
  useEffect(() => {
    if (!initial) return
    api.get(`/api/tasks/${initial.id}`)
      .then((t) => {
        setName(t.name)
        setConfig(t.config || {})
        setAction(t.action)
        setPreActions(t.pre_actions || [])
        const cron = t.schedule?.cron || ''
        const matched = CRON_PRESETS.find((p) => p.value === cron)
        if (matched) setCronMode(cron)
        else { setCronMode('custom'); setCronText(cron) }
        setCronEnabled(!!t.schedule?.enabled)
        setDeliveryType(t.delivery?.type || 'none')
        setDeliveryTo((t.delivery?.to || []).join(','))
        setFeishuWebhook(t.delivery?.webhook || '')
        setRetryCount(t.retry_count || 0)
        setExportTimeout(t.export_timeout || 180)
        return api.get(`/api/profiles/${t.profile_id}`)
      })
      .then((p) => { if (p) setProfile(p) })
      .catch((e) => console.error(e))
  }, [initial])

  const fields = useMemo(
    () => (profile?.fields || []).filter((f) => f.included !== false),
    [profile]
  )
  const actions = useMemo(
    () => (profile?.actions || []).filter((a) => a.included !== false),
    [profile]
  )

  const submit = async () => {
    if (!profile) return message.warning('请选择页面档案')
    if (!name) return message.warning('请填写任务名称')
    if (!action) return message.warning('请选择执行动作')
    // 仅在定时启用时校验 cron（未启用时允许为空，编辑旧任务不再被卡住）
    if (cronEnabled && cronMode === 'custom' && !/^\S+\s+\S+\s+\S+\s+\S+\s+\S+$/.test(cronText.trim())) {
      return message.warning('请输入合法的 cron 表达式（5 段）')
    }
    const cron = cronEnabled ? (cronMode === 'custom' ? cronText.trim() : cronMode) : ''
    let delivery = { type: 'none' }
    if (deliveryType === 'email' && deliveryTo) {
      delivery = { type: 'email', to: deliveryTo.split(/[,，\s]+/).filter(Boolean) }
    } else if (deliveryType === 'feishu' && feishuWebhook) {
      delivery = { type: 'feishu', webhook: feishuWebhook.trim() }
    }
    const payload = {
      name,
      profile_id: profile.id,
      config,
      pre_actions: preActions.filter((a) => a !== action),
      action,
      schedule: { enabled: cronEnabled, cron: cronEnabled ? cron : '' },
      delivery,
      retry_count: retryCount,
      export_timeout: exportTimeout
    }
    try {
      if (initial) {
        await api.put(`/api/tasks/${initial.id}`, payload)
      } else {
        await api.post('/api/tasks', payload)
      }
      if (onSaved) onSaved()
      else navigate('/tasks')
    } catch (e) {
      message.error(e.message)
    }
  }

  if (!initial && noProfiles) {
    return (
      <div style={{ padding: '24px 0' }}>
        <p>暂无已确认的页面档案。请先通过「接入向导」解析目标页面并确认字段。</p>
        <Button type="primary" onClick={() => navigate('/wizard')}>
          前往接入向导
        </Button>
      </div>
    )
  }

  return (
    <Form layout="vertical" style={{ maxWidth: 720 }}>
      <Form.Item label="页面档案" required>
        {initial ? (
          <Input value={`#${profile?.id} ${profile?.target_url || ''}`} disabled />
        ) : (
          <Select
            value={profile?.id}
            options={profileList.map((p) => ({
              label: `#${p.id} ${p.target_url}${p.confirmed ? '' : '（未确认）'}`,
              value: p.id,
              disabled: !p.confirmed
            }))}
            onChange={(id) => setProfile(profileList.find((p) => p.id === id))}
          />
        )}
      </Form.Item>

      <Form.Item label="任务名称" required>
        <Input
          placeholder="如：华东周报导出" value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </Form.Item>

      <Divider orientation="left">
        业务条件（来自网页解析：<Tag color="purple">{fields.length} 个可选字段</Tag>）
      </Divider>
      {fields.length === 0 && <p>该页面未识别出可配置字段</p>}
      {fields.map((f) => (
        <Form.Item key={f.key} label={f.semantic_name}>
          <FieldControl
            field={f}
            value={config[f.semantic_name]}
            onChange={(v) => setConfig({ ...config, [f.semantic_name]: v })}
          />
        </Form.Item>
      ))}

      <Divider orientation="left">执行动作</Divider>
      <Form.Item label="主动作" required>
        <Select
          style={{ width: 280 }}
          placeholder="如：导出 Excel"
          options={actions.map((a) => ({ label: `${a.semantic_name}（${a.kind}）`, value: a.semantic_name }))}
          value={action}
          onChange={setAction}
        />
      </Form.Item>
      <Form.Item label="前置动作（如：先查询后导出）">
        <Select
          mode="multiple" style={{ width: 380 }} allowClear
          placeholder="可选"
          options={actions.map((a) => ({ label: a.semantic_name, value: a.semantic_name }))}
          value={preActions}
          onChange={setPreActions}
        />
      </Form.Item>

      <Divider orientation="left">运行频率</Divider>
      <Space direction="vertical" size={12}>
        <Radio.Group value={cronMode} onChange={(e) => setCronMode(e.target.value)}>
          {CRON_PRESETS.map((p) => (
            <Radio.Button key={p.value} value={p.value}>{p.label}</Radio.Button>
          ))}
        </Radio.Group>
        {cronMode === 'custom' && (
          <Input
            style={{ width: 280 }} placeholder="0 9 * * 1（分 时 日 月 周）"
            value={cronText} onChange={(e) => setCronText(e.target.value)}
          />
        )}
        <Space>
          <span>定时启用：</span>
          <Switch checked={cronEnabled} onChange={setCronEnabled} />
        </Space>
      </Space>

      <Divider orientation="left">结果通知</Divider>
      <Radio.Group value={deliveryType} onChange={(e) => setDeliveryType(e.target.value)}>
        <Radio.Button value="none">暂不通知</Radio.Button>
        <Radio.Button value="email">邮件</Radio.Button>
        <Radio.Button value="feishu">飞书群机器人</Radio.Button>
      </Radio.Group>
      {deliveryType === 'email' && (
        <Form.Item style={{ marginTop: 12 }}>
          <Input
            style={{ width: 380 }} placeholder="收件邮箱，多个用逗号分隔"
            value={deliveryTo} onChange={(e) => setDeliveryTo(e.target.value)}
          />
        </Form.Item>
      )}
      {deliveryType === 'feishu' && (
        <Form.Item style={{ marginTop: 12 }}>
          <Input
            style={{ width: 480 }} placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/…"
            value={feishuWebhook} onChange={(e) => setFeishuWebhook(e.target.value)}
          />
        </Form.Item>
      )}

      <Divider orientation="left">可靠性</Divider>
      <Space align="center" size={12}>
        <span>失败自动重试次数：</span>
        <InputNumber
          min={0} max={5} value={retryCount}
          onChange={(v) => setRetryCount(v || 0)}
        />
        <Typography.Text type="secondary">
          执行失败后自动重试（0~5 次），重试时强制重新登录；连续 2 次失败将按通知方式告警
        </Typography.Text>
      </Space>
      <Space align="center" size={12} style={{ marginTop: 12 }}>
        <span>导出等待上限（秒）：</span>
        <InputNumber
          min={30} max={3600} step={60} value={exportTimeout}
          onChange={(v) => setExportTimeout(v || 180)}
        />
        <Typography.Text type="secondary">
          导出中心异步生成文件的场景，生成可能需数分钟，建议 600 秒以上
        </Typography.Text>
      </Space>

      <Divider />
      <Space>
        <Button type="primary" onClick={submit}>
          {initial ? '保存修改' : '创建任务'}
        </Button>
        <Button onClick={() => navigate('/tasks')}>取消</Button>
      </Space>
    </Form>
  )
}
