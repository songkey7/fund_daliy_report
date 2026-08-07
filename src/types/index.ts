export interface PushTask {
  id: string
  name: string
  cron: string
  enabled: boolean
  messageData: () => Promise<void>
}
