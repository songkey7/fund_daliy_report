import axios, { AxiosInstance } from 'axios'

export interface WecomBotConfig {
  webhookUrl: string
}

export interface DingBotConfig {
  webhookUrl: string
  secret?: string
}

export class PushService {
  private http: AxiosInstance

  constructor() {
    this.http = axios.create({ timeout: 10000 })
  }

  async sendPushPlus(
    token: string,
    title: string,
    content: string
  ): Promise<boolean> {
    const url = 'https://www.pushplus.plus/send/'
    // template: 'html' makes the content show properly in WeChat
    const { data } = await this.http.post(url, {
      token,
      title,
      content,
      template: 'html',
    })
    return data?.code === 200
  }

  async sendWecomBot(
    webhookUrl: string,
    content: string
  ): Promise<boolean> {
    const { data } = await this.http.post(webhookUrl, {
      msgtype: 'markdown',
      markdown: { content },
    })
    return data?.errcode === 0
  }

  async sendDingBot(
    webhookUrl: string,
    title: string,
    content: string,
    secret?: string
  ): Promise<boolean> {
    let url = webhookUrl
    if (secret) {
      const crypto = await import('crypto')
      const timestamp = Date.now()
      const sign = crypto
        .createHmac('sha256', secret)
        .update(`${timestamp}\n${secret}`)
        .digest('base64')
      url = `${webhookUrl}&timestamp=${timestamp}&sign=${encodeURIComponent(sign)}`
    }
    const { data } = await this.http.post(url, {
      msgtype: 'markdown',
      markdown: { title, text: content },
    })
    return data?.errcode === 0
  }
}

export const pushService = new PushService()
