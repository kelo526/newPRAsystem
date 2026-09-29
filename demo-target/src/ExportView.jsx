import React, { useState } from 'react'
import { Layout, Card, Button, message, Typography, Space, Tag } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { buildMockOrders } from './mockData'

const { Header, Content } = Layout
const { Title, Paragraph } = Typography

export default function ExportView() {
  const [downloading, setDownloading] = useState(false)

  const handleDownload = async () => {
    setDownloading(true)
    await new Promise((r) => setTimeout(r, 1500))
    const rows = buildMockOrders()
    const header = ['订单编号', '订单日期', '区域', '产品类型', '订单状态', '数量', '金额']
    const lines = [header.join(','), ...rows.map((o) =>
      [o.id, o.date, o.region, o.productType, o.status, o.qty, o.amount].join(',')
    )]
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `订单报表_新窗口_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`
    a.click()
    URL.revokeObjectURL(url)
    setDownloading(false)
    message.success('文件已下载')
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#001529',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px'
        }}
      >
        <span style={{ color: '#fff', fontSize: 16, fontWeight: 500 }}>
          订单经营管理系统 · 报表中心
        </span>
      </Header>
      <Content style={{ padding: 48, display: 'flex', justifyContent: 'center' }}>
        <Card style={{ width: 520, textAlign: 'center' }}>
          <Title level={4} style={{ marginTop: 0 }}>报表已生成</Title>
          <Paragraph type="secondary">
            您提交的导出请求已处理完成。
          </Paragraph>
          <Space direction="vertical" size={8} style={{ marginBottom: 24 }}>
            <div><Tag>数据量：{buildMockOrders().length} 条</Tag></div>
            <div><Tag color="green">状态：已生成</Tag></div>
          </Space>
          <Button
            type="primary"
            size="large"
            icon={<DownloadOutlined />}
            loading={downloading}
            onClick={handleDownload}
          >
            下载文件
          </Button>
        </Card>
      </Content>
    </Layout>
  )
}
