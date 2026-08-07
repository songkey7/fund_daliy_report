export const messageTemplates = {
  fundAlert: {
    name: '基金异动提醒',
    format: (data: {
      fundName: string
      netValue: string
      changePercent: string
      time: string
    }) =>
      `## 📊 基金净值异动提醒\n\n` +
      `> **基金名称**: ${data.fundName}\n` +
      `> **最新净值**: ${data.netValue}\n` +
      `> **涨跌幅**: ${data.changePercent}\n` +
      `> **更新时间**: ${data.time}`,
  },

  dailyReport: {
    name: '投资日报',
    format: (data: {
      date: string
      marketIndex: string
      fundPerformance: string
      mainNews: string
    }) =>
      `## 📈 投资日报 (${data.date})\n\n` +
      `> **市场指数**: ${data.marketIndex}\n` +
      `> **基金表现**: ${data.fundPerformance}\n` +
      `> **今日要点**: ${data.mainNews}`,
  },

  marketOpen: {
    name: '开盘提醒',
    format: () =>
      `## ⏰ 市场开盘提醒\n\n` +
      `A股市场今日开盘在即，祝您投资顺利！`,
  },
}
