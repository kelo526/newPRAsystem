import React, { useMemo, useState } from 'react'
import { Layout, Card, Form, Input, Select, DatePicker, Button, Table, Space, message, Typography } from 'antd'
import { SearchOutlined, ReloadOutlined, DownloadOutlined, LogoutOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { buildMockOrders, REGIONS, ORDER_STATUS, PRODUCT_TYPES, CHANNELS, BIZ_LINES } from './mockData'

const { RangePicker } = DatePicker
const { Title } = Typography
const { Header, Content } = Layout

const ALL_ORDERS = buildMockOrders()

export const DATA_SCOPES = ['全部数据', '仅异常', '仅补录']

export default function Report() {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const [filtered, setFiltered] = useState(ALL_ORDERS)
  const [exporting, setExporting] = useState(false)

  const handleQuery = () => {
    const v = form.getFieldsValue()
    const rows = ALL_ORDERS.filter((o) => {
      if (v.dateRange && v.dateRange.length === 2) {
        const [start, end] = v.dateRange
        const d = dayjs(o.date)
        if (d.isBefore(start, 'day') || d.isAfter(end, 'day')) return false
      }
      if (v.region?.length && !v.region.includes(o.region)) return false
      if (v.status && o.status !== v.status) return false
      if (v.productType && o.productType !== v.productType) return false
      if (v.channel && o.channel !== v.channel) return false
      if (v.bizLine && o.bizLine !== v.bizLine) return false
      if (v.dataScope === '仅异常' && o.status !== '已取消') return false
      if (v.dataScope === '仅补录' && o.status !== '待处理') return false
      if (v.keyword && !o.id.includes(v.keyword.trim())) return false
      return true
    })
    setFiltered(rows)
    message.success(`查询完成，共 ${rows.length} 条`)
  }

  const handleReset = () => {
    form.resetFields()
    setFiltered(ALL_ORDERS)
  }

  const handleExport = async () => {
    setExporting(true)
    // 模拟后端生成文件的延迟
    await new Promise((r) => setTimeout(r, 2000))
    const header = ['订单编号', '订单日期', '区域', '产品类型', '订单状态', '数量', '金额']
    const lines = [header.join(','), ...filtered.map((o) =>
      [o.id, o.date, o.region, o.productType, o.status, o.qty, o.amount].join(',')
    )]
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `订单报表_${dayjs().format('YYYYMMDD_HHmmss')}.csv`
    a.click()
    URL.revokeObjectURL(url)
    setExporting(false)
    message.success('导出成功')
  }

  const handleLogout = () => {
    localStorage.removeItem('demo_token')
    navigate('/login')
  }

  const columns = useMemo(
    () => [
      { title: '订单编号', dataIndex: 'id', key: 'id', width: 200 },
      { title: '订单日期', dataIndex: 'date', key: 'date', width: 120 },
      { title: '区域', dataIndex: 'region', key: 'region', width: 90 },
      { title: '产品类型', dataIndex: 'productType', key: 'productType', width: 110 },
      { title: '渠道', dataIndex: 'channel', key: 'channel', width: 90 },
      { title: '业务线', dataIndex: 'bizLine', key: 'bizLine', width: 100 },
      { title: '订单状态', dataIndex: 'status', key: 'status', width: 110 },
      { title: '数量', dataIndex: 'qty', key: 'qty', width: 90 },
      { title: '金额（元）', dataIndex: 'amount', key: 'amount', width: 120 }
    ],
    []
  )

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
          订单经营管理系统
        </span>
        <Button
          type="text"
          icon={<LogoutOutlined />}
          style={{ color: '#fff' }}
          onClick={handleLogout}
        >
          退出登录
        </Button>
      </Header>
      <Content style={{ padding: 24 }}>
        <Card>
          <Title level={4} style={{ marginTop: 0 }}>
            订单经营报表
          </Title>
          <Form
            form={form}
            layout="inline"
            initialValues={{ dateRange: [dayjs().subtract(30, 'day'), dayjs()] }}
          >
            <Form.Item label="统计日期" name="dateRange">
              <RangePicker allowEmpty={[false, false]} />
            </Form.Item>
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
            <Form.Item label="产品类型" name="productType">
              <Select
                placeholder="请选择产品类型"
                options={PRODUCT_TYPES.map((p) => ({ label: p, value: p }))}
                style={{ minWidth: 140 }}
                allowClear
              />
            </Form.Item>
            <Form.Item label="渠道" name="channel">
              <Select
                placeholder="请选择渠道"
                options={CHANNELS.map((c) => ({ label: c, value: c }))}
                style={{ minWidth: 130 }}
                allowClear
              />
            </Form.Item>
            <Form.Item label="数据范围" name="dataScope">
              <Select
                placeholder="请选择数据范围"
                options={DATA_SCOPES.map((s) => ({ label: s, value: s }))}
                style={{ minWidth: 140 }}
                allowClear
              />
            </Form.Item>
            <Form.Item label="业务线" name="bizLine">
              <Select
                placeholder="请选择业务线"
                options={BIZ_LINES.map((b) => ({ label: b, value: b }))}
                style={{ minWidth: 130 }}
                allowClear
              />
            </Form.Item>
            <Form.Item label="订单编号" name="keyword">
              <Input placeholder="请输入订单编号" style={{ width: 180 }} allowClear />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" icon={<SearchOutlined />} onClick={handleQuery}>
                  查询
                </Button>
                <Button icon={<ReloadOutlined />} onClick={handleReset}>
                  重置
                </Button>
                <Button
                  type="primary"
                  ghost
                  icon={<DownloadOutlined />}
                  loading={exporting}
                  onClick={handleExport}
                >
                  导出 Excel
                </Button>
              </Space>
            </Form.Item>
          </Form>
          <Table
            style={{ marginTop: 16 }}
            columns={columns}
            dataSource={filtered}
            pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条` }}
            size="middle"
          />
        </Card>
      </Content>
    </Layout>
  )
}
