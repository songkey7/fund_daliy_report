import schedule from 'node-schedule'
import winston from 'winston'
import type { PushTask } from '../types'

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.printf(({ timestamp, level, message }) =>
      `[${timestamp}] ${level.toUpperCase()}: ${message}`
    )
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'logs/scheduler.log' }),
  ],
})

type JobRef = schedule.Job | null

class ScheduleManager {
  private jobs: Map<string, schedule.Job> = new Map()
  private tasks: Map<string, PushTask> = new Map()

  registerTask(task: PushTask): void {
    this.tasks.set(task.id, task)

    if (!task.enabled) return

    const job = schedule.scheduleJob(task.cron, () => {
      this.executeTask(task.id)
    })

    if (job) {
      this.jobs.set(task.id, job)
      logger.info(`任务注册成功: ${task.name} (${task.cron})`)
    }
  }

  async executeTask(taskId: string): Promise<void> {
    const task = this.tasks.get(taskId)
    if (!task) {
      logger.error(`任务未找到: ${taskId}`)
      return
    }

    logger.info(`执行任务: ${task.name}`)

    try {
      if (typeof task.messageData === 'function') {
        const result = await task.messageData()
        logger.info(`任务执行成功: ${task.name}, 数据: ${JSON.stringify(result)}`)
      }
    } catch (err) {
      logger.error(`任务执行失败: ${task.name}, 错误: ${err}`)
    }
  }

  removeTask(taskId: string): void {
    const job = this.jobs.get(taskId)
    if (job) {
      job.cancel()
      this.jobs.delete(taskId)
    }
    this.tasks.delete(taskId)
    logger.info(`任务已移除: ${taskId}`)
  }

  startTask(taskId: string): void {
    const task = this.tasks.get(taskId)
    if (!task) return

    task.enabled = true
    const existing = this.jobs.get(taskId)
    if (existing) {
      existing.reschedule(task.cron)
    } else {
      const job = schedule.scheduleJob(task.cron, () => {
        this.executeTask(task.id)
      })
      if (job) {
        this.jobs.set(taskId, job)
      }
    }

    logger.info(`任务已启用: ${task.name}`)
  }

  stopTask(taskId: string): void {
    const job = this.jobs.get(taskId)
    if (job) {
      job.cancel()
    }
    const task = this.tasks.get(taskId)
    if (task) {
      task.enabled = false
    }
    logger.info(`任务已停止: ${taskId}`)
  }

  getTaskStatus(): Array<{ id: string; name: string; enabled: boolean; cron: string }> {
    return Array.from(this.tasks.values()).map(task => ({
      id: task.id,
      name: task.name,
      enabled: task.enabled,
      cron: task.cron,
    }))
  }
}

export const scheduleManager = new ScheduleManager()
