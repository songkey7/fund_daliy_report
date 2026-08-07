import axios from 'axios'
import fs from 'fs'
import path from 'path'

interface FundRecord {
  id: string
  buyDate: string
  amount: number
  stopLoss: number
  stopProfit: number
}

interface FundPerformance {
  name: string
  code: string
  daily: string
  weekly: string
  monthly: string
  quarterly: string
  halfYearly: string
  yearly: string
  ytd: string
}

function parseFundRecords(): FundRecord[] {
  const filePath = path.resolve(__dirname, '../../fund.txt')
  const content = fs.readFileSync(filePath, 'utf-8')
  const lines = content.trim().split('\n').slice(1)
  return lines.map(line => {
    const [id, buyDate, amount, stopLoss, stopProfit] = line.trim().split(',')
    return { id: id.trim(), buyDate: buyDate.trim(), amount: Number(amount), stopLoss: Number(stopLoss), stopProfit: Number(stopProfit) }
  })
}

async function fetchFundNAV(code: string): Promise<{ name: string; data: Array<{ date: string; nav: number }> }> {
  // 取最近 2 年数据
  const url = `https://lh.qmawe.com/chartedge/api/fund?code=${code}&range=2y`
  const { data } = await axios.get(url, { timeout: 15000 })
  const items = data?.data?.data

  if (!items || items.length === 0) {
    throw new Error(`No data for ${code}`)
  }

  const name = items.map((item: any) => item.name).find(Boolean) ?? data?.data?.fundName ?? code
  const navData = items.map((item: any) => {
    const d = item.date ?? item.tx_date ?? item.fund_date ?? ''
    const nav = Number(item.nav ?? item.unit_nav ?? item.netValue ?? item.nav_value ?? 0)
    return { date: String(d), nav }
  })
  // 去重（按日期降序排列取最新）
  const map = new Map<string, number>()
  for (const { date, nav } of navData) {
    if (date && nav > 0 && !map.has(date)) {
      map.set(date, nav)
    }
  }
  const sorted = Array.from(map.entries())
    .sort((a, b) => (a[0] > b[0] ? -1 : 1))
  return { name, data: sorted.map(([date, nav]) => ({ date, nav })) }
}

function calcChange(data: Array<{ date: string; nav: number }>, daysBack: number): string {
  const target = data[0]
  const base = data[Math.min(daysBack, data.length - 1)]
  const change = ((target.nav - base.nav) / base.nav * 100).toFixed(2)
  return change
}

function dateToStr(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function getDateOffset(base: Date, offsetDays: number): string {
  const d = new Date(base)
  d.setDate(d.getDate() - offsetDays)
  return dateToStr(d)
}

// ========== 用日期在已拉取数据中找对应 NAV ==========
// 原代码保持不变

// 写入口时将原 main func 放在后面

// ========== 主函数 ==========
async function main() {
  const records = parseFundRecords()

  for (const record of records) {
    console.log(`\n========== ${record.id} ==========`)
    try {
      const { name, data } = await fetchFundNAV(record.id)
      const latestDate = data[0].date

      // 当天 NAV
      const latest = data[0].nav
      // calcChange 需定义
      const d1 = calcChange(data, 1)
      const w = calcChange(data, 5)
      const m = calcChange(data, 22)
      const q = calcChange(data, 66)
      const h = calcChange(data, 126)
      const y = calcChange(data, 252)
      const ytd_ = calcChange(data, 365)

      console.log(`名称: ${name}`)
      console.log(`净值日期: ${latestDate}, 净值: ${latest}`)
      console.log(`日涨跌 (D1): ${d1}%`)
      console.log(`周涨跌 (WOW): ${w}%`)
      console.log(`月涨跌 (MOM): ${m}%`)
      console.log(`季涨跌 (QOQ): ${q}%`)
      console.log(`半年涨跌 (HOH): ${h}%`)
      console.log(`年涨跌 (YOY): ${y}%`)
      console.log(`YTD 涨跌: ${ytd_}%`)
      console.log(`购买日期: ${record.buyDate}, 金额: ${record.amount}, 止损: ${record.stopLoss}%, 止盈: ${record.stopProfit}%`)
    } catch (e: any) {
      console.error(`查询 ${record.id} 失败: ${e.message}`)
    }
  }
}

main()
