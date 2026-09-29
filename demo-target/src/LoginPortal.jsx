import React from 'react'
import { Layout, Card, Button, Typography, Row, Col } from 'antd'
import { LoginOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

const { Header, Content } = Layout
const { Title } = Typography

export default function LoginPortal() {
  const navigate = useNavigate()

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
          XX 集团统一门户（两步式登录演示）
        </span>
      </Header>
      <Content style={{ padding: 64, display: 'flex', justifyContent: 'center' }}>
        <Row gutter={[24, 24]}>
          <Col>
            <Card style={{ width: 320, textAlign: 'center' }} hoverable>
              <Title level={4} style={{ marginTop: 0 }}>订单经营管理系统</Title>
              <p style={{ color: '#888' }}>经营报表查询与导出</p>
              <Button
                type="primary"
                icon={<LoginOutlined />}
                onClick={() => navigate('/login')}
              >
                进入系统
              </Button>
            </Card>
          </Col>
          <Col>
            <Card style={{ width: 320, textAlign: 'center' }}>
              <Title level={4} style={{ marginTop: 0 }}>其他业务系统</Title>
              <p style={{ color: '#888' }}>（演示占位，未接入）</p>
              <Button disabled icon={<LoginOutlined />}>进入系统</Button>
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}
