import dayjs from 'dayjs'

// 确定性伪随机（种子固定，每次刷新数据一致，便于自动化验证）
function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const REGIONS = ['华东', '华南', '华北', '西南', '西北', '东北']
export const ORDER_STATUS = ['待处理', '处理中', '已完成', '已取消']
export const PRODUCT_TYPES = ['手机', '平板', '笔记本', '穿戴', '配件']
export const CHANNELS = ['线上', '门店', '电商']
export const BIZ_LINES = ['全渠道', '线上直营', '运营商', '政企']

export function buildMockOrders(count = 200) {
  const rand = mulberry32(20260915)
  const today = dayjs()
  const orders = []
  for (let i = 0; i < count; i++) {
    const daysAgo = Math.floor(rand() * 90)
    const date = today.subtract(daysAgo, 'day')
    const qty = 1 + Math.floor(rand() * 20)
    orders.push({
      key: i,
      id: `ORD-${date.format('YYYYMMDD')}-${String(i + 1).padStart(4, '0')}`,
      date: date.format('YYYY-MM-DD'),
      region: REGIONS[Math.floor(rand() * REGIONS.length)],
      productType: PRODUCT_TYPES[Math.floor(rand() * PRODUCT_TYPES.length)],
      status: ORDER_STATUS[Math.floor(rand() * ORDER_STATUS.length)],
      channel: CHANNELS[Math.floor(rand() * CHANNELS.length)],
      bizLine: BIZ_LINES[Math.floor(rand() * BIZ_LINES.length)],
      qty,
      amount: Math.round(qty * (500 + rand() * 8000))
    })
  }
  return orders
}
