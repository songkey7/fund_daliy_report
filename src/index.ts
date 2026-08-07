import 'dotenv/config'
import express from 'express'
import winston from 'winston'
import config from './config'
import { pushService } from './push'
import { scheduleManager } from './scheduler'
import { messageTemplates } from './templates'
import { createRoutes } from './routes'

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.printf(({ timestamp, level, message }) =>
      `[${timestamp}] ${level.toUpperCase()}: ${message}`
    )
  ),
  transports: [new winston.transports.Console()],
})

async function main() {
  if (!config.pushPlus.token) {
    logger.warn('⚠ 未配置 PUSHPLUS_TOKEN，请在 .env 中配置')
  }

  // ========== 示例：开盘提醒任务 ==========
  scheduleManager.registerTask({
    id: 'marketOpen',
    name: '开盘提醒',
    cron: config.tasks.dailyReport.cron,
    enabled: false, // 默认关闭，需要时改为 true
    messageData: async () => {
      const title = '市场开盘提醒'
      const content = messageTemplates.marketOpen.format()
      const ok = await pushService.sendPushPlus(config.pushPlus.token, title, content)
      logger.info(`[开盘提醒] 推送${ok ? '成功' : '失败'}`)
    },
  })

  // ========== 示例：投资日报任务 ==========
  scheduleManager.registerTask({
    id: 'dailyReport',
    name: '投资日报',
    cron: config.tasks.dailyReport.cron,
    enabled: true,
    messageData: async () => {
      const data = {
        date: new Date().toLocaleDateString('zh-CN'),
        marketIndex: '上证 3250.20 (+0.5%), 深成 10943.81 (+1.2%)',
        fundPerformance: '组合: 日涨幅 +0.85%，累计 +12.3%',
        mainNews: '暂无重要新闻',
      }
      const title = `投资日报 ${data.date}`
      const content = messageTemplates.dailyReport.format(data)
      const ok = await pushService.sendPushPlus(config.pushPlus.token, title, content)
      logger.info(`[投资日报] 推送${ok ? '成功' : '失败'}`)
    },
  })

  const app = express()
  app.use(express.json())
  app.use('/api', createRoutes())

  app.listen(config.port, () => {
    logger.info(`消息推送系统启动成功: http://localhost:${config.port}`)
    logger.info(`已注册 ${scheduleManager.getTaskStatus().length} 个定时任务`)
  })
}

main().catch(err => {
  logger.error(`系统启动失败: ${err}`)
  process.exit(1)
})
