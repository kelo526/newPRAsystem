import React, { useState } from 'react'
import {
  Layout, Card, Form, Select, Button, Table, Space, message, Modal, Tag, Typography
} from 'antd'
import {
  SearchOutlined, DownloadOutlined, CloudDownloadOutlined,
  ExportOutlined, ScheduleOutlined
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { buildMockOrders, REGIONS, ORDER_STATUS } from './mockData'

const { Header, Content } = Layout
const { Title } = Typography

const LS_KEY = 'demo_export_records'

function loadRecords() {
  const raw = localStorage.getItem(LS_KEY)
  if (!raw) {
    // 预置两条"其他同事"的历史记录，模拟共享导出中心（新记录插最前）
    const preset = [
      { id: 2, name: '订单报表_同事提交_20260918_093000.csv', time: '2026-09-18 09:30:00', status: '已生成' },
      { id: 1, name: '订单报表_同事提交_20260917_180000.csv', time: '2026-09-17 18:00:00', status: '已生成' }
    ]
    localStorage.setItem(LS_KEY, JSON.stringify(preset))
    return preset
  }
  return JSON.parse(raw)
}

export default function ExportDemo() {
  const [form] = Form.useForm()
  const [allOrders] = useState(buildMockOrders)
  const [filtered, setFiltered] = useState(buildMockOrders())
  const [records, setRecords] = useState(loadRecords)
  const [modalOpen, setModalOpen] = useState(false)
  const [busy, setBusy] = useState({})

  const handleQuery = () => {
    const v = form.getFieldsValue()
    const rows = allOrders.filter((o) => {
      if (v.region?.length && !v.region.includes(o.region)) return false
      if (v.status && o.status !== v.status) return false
      return true
    })
    setFiltered(rows)
    message.success(`查询完成，共 ${rows.length} 条`)
  }

  const toCsvBlob = (rows) => {
    const header = ['订单编号', '订单日期', '区域', '产品类型', '订单状态', '数量', '金额']
    const lines = [header.join(','), ...rows.map((o) =>
      [o.id, o.date, o.region, o.productType, o.status, o.qty, o.amount].join(',')
    )]
    return new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  }

  const triggerDownload = (rows, name) => {
    const url = URL.createObjectURL(toCsvBlob(rows))
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  }

  // 模式 A：直接导出（点击即下载）
  const exportDirect = async () => {
    setBusy((b) => ({ ...b, direct: true }))
    await new Promise((r) => setTimeout(r, 1500))
    triggerDownload(filtered, `订单报表_直接_${dayjs().format('YYYYMMDD_HHmmss')}.csv`)
    setBusy((b) => ({ ...b, direct: false }))
    message.success('导出成功')
  }

  // 模式 B：新窗口导出（点击后跳转报表中心新页，再点下载）
  const exportNewWindow = () => {
    window.open(`${window.location.origin}/export-view`, '_blank')
    message.info('已在新窗口打开报表中心')
  }

  // 模式 C：弹窗确认导出
  const exportModal = () => {
    setModalOpen(true)
  }
  const confirmModalDownload = () => {
    setModalOpen(false)
    triggerDownload(filtered, `订单报表_弹窗_${dayjs().format('YYYYMMDD_HHmmss')}.csv`)
    message.success('导出成功')
  }

  // 模式 D：异步导出任务（大数据量延迟生成，出现在共享导出中心）
  const submitExportTask = () => {
    const id = Date.now()
    const name = `订单报表_异步任务_${dayjs().format('YYYYMMDD_HHmmss')}.csv`
    const rec = { id, name, time: dayjs().format('YYYY-MM-DD HH:mm:ss'), status: '生成中' }
    setRecords((rs) => [rec, ...rs])
    message.info('导出任务已提交，请到下方导出中心等待生成')
    // 模拟大数据量生成耗时 12 秒
    setTimeout(() => {
      setRecords((rs) => rs.map((r) => (r.id === id ? { ...r, status: '已生成' } : r)))
    }, 12000)
  }

  const downloadRecord = (rec) => {
    triggerDownload(filtered, rec.name)
    message.success('文件已下载')
  }

  const recordColumns = [
    { title: '文件名', dataIndex: 'name', ellipsis: true },
    { title: '提交时间', dataIndex: 'time', width: 170 },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (s) => s === '已生成'
        ? <Tag color="green">已生成</Tag>
        : <Tag color="orange">生成中…</Tag>
    },
    {
      title: '操作', width: 110,
      render: (_, rec) =>
        rec.status === '已生成' ? (
          <Button size="small" icon={<DownloadOutlined />} onClick={() => downloadRecord(rec)}>
            下载
          </Button>
        ) : (
          <Button size="small" disabled loading>生成中</Button>
        )
    }
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#001529',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px'
        }}
      >
        <span style={{ color: '#fff', fontSize: 16, fontWeight: 500 }}>
          订单经营管理系统 · 导出中心演示
        </span>
        <Tag color="gold">四种企业导出模式</Tag>
      </Header>
      <Content style={{ padding: 24 }}>
        <Card>
          <Title level={4} style={{ marginTop: 0 }}>订单经营报表</Title>
          <Form form={form} layout="inline">
            <Form.Item label="区域" name="region">
              <Select
                mode="multiple"
                placeholder="请选择区域"
                options={REGIONS.map((r) => ({ label: r, value: r }))}
                style={{ minWidth: 180 }}
                allowClear
              />
            </Form.Item>
            <Form.Item label="订单状态" name="status">
              <Select
                placeholder="请选择状态"
                options={ORDER_STATUS.map((s) => ({ label: s, value: s }))}
                style={{ minWidth: 140 }}
                allowClear
              />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" icon={<SearchOutlined />} onClick={handleQuery}>
                  查询
                </Button>
                <Button icon={<DownloadOutlined />} loading={busy.direct} onClick={exportDirect}>
                  导出 Excel
                </Button>
                <Button icon={<ExportOutlined />} onClick={exportNewWindow}>
                  导出（新窗口）
                </Button>
                <Button icon={<DownloadOutlined />} onClick={exportModal}>
                  导出（弹窗确认）
                </Button>
                <Button type="primary" ghost icon={<ScheduleOutlined />} onClick={submitExportTask}>
                  提交导出任务
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>

        <Card title="导出中心（所有用户共享，异步生成）" style={{ marginTop: 16 }}>
          <Table
            rowKey="id"
            size="middle"
            columns={recordColumns}
            dataSource={records}
            pagination={{ pageSize: 8 }}
          />
        </Card>

        <Modal
          title="确认导出"
          open={modalOpen}
          onOk={confirmModalDownload}
          onCancel={() => setModalOpen(false)}
          okText="确认下载"
          cancelText="取消"
        >
          <p>
            即将导出当前筛选结果，共 <b>{filtered.length}</b> 条数据，
            文件为 CSV 格式。是否确认下载？
          </p>
        </Modal>
      </Content>
    </Layout>
  )
}
