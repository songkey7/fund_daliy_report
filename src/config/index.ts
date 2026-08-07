import dotenv from 'dotenv'
dotenv.config()

export default {
  port: parseInt(process.env.PORT || '3000', 10),

  pushPlus: {
    token: process.env.PUSHPLUS_TOKEN || '',
  },

  wecomBot: {
    webhookUrl: process.env.WECOM_WEBHOOK || '',
  },

  dingBot: {
    webhookUrl: process.env.DING_WEBHOOK || '',
    secret: process.env.DING_SECRET || '',
  },

  tasks: {
    dailyReport: { cron: '0 18 * * 1-5', enabled: true },
    fundAlert: { cron: '*/30 * * * *', enabled: false },
  },
}
