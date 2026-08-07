# ⏰ 基金消息推送系统

通过 **Server酱** 将基金异动提醒、投资日报等消息推送到你的微信。

## 快速开始

### 1. 获取 Server酱 SendKey

访问 [https://sct.ftqq.com](https://sct.ftqq.com)，扫码登录 → 获得 SendKey。

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 SendKey：

```env
SERVER_KEY=你的SCT密钥
```

### 3. 运行

```bash
npm install
npm run dev
```

## 自定义消息任务

### 注册消息任务

在 `src/index.ts` 中注册新的消息任务：

```typescript
scheduleManager.registerTask({
  id: 'fundAlert',
  name: '基金净動异动提醒',
  cron: '*/30 * * * *',  // 每30分钟
  enabled: true,
  messageData: async () => {
    // 1. 在这里写你的业务逻辑，例如调用基金数据 API
    // const data = await fetchSomeFundData('000001')
    //
    // 2. 推送消息
    await pushService.sendServerChan(
      '你的SendKey',
      '基金异动提醒',
      '标题\n\n内容'
    )
  },
})
```

### 在 async 回调中完成以下步骤：

1. **获取数据**：调用 Tushare / AKShare / 东方财富 API 等数据源
2. **条件判断**：设置涨跌阈值，只有触发阈值才推送
3. **推送消息**：`pushService.sendServerChan()` 推送到微信
4. **调试**：检查 `logs/scheduler.log` 查看错误

## 消息模板

所有模板位于 `src/templates/MessageTemplates.ts`：

```typescript
import { pushService } from './push'
import { messageTemplates } from './templates'

// 基金异动提醒
const content = messageTemplates.fundAlert.format({ /* ... */ })

// 投资日报
const content2 = messageTemplates.dailyReport.format({ /* ... */ })

// 发送到微信
await pushService.sendServerChan(key, '标题', content)
```

---

## 可选的推送渠道

### 企业微信机器人

在 `.env` 中添加 webhook URL：

```env
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

```typescript
await pushService.sendWecomBot(webhookUrl, '## 标题\n\n内容')
```

### 钉钉机器人

```env
DING_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DING_SECRET=your_secret（可选）
```

```typescript
await pushService.sendDingBot(webhookUrl, '标题', '内容', secret)
```

---

## 项目结构

```text
src/
├── index.ts              # 入口，注册定时任务
├── push/PushService.ts    # 推送服务（Server酱、企业微信、钉钉）
├── scheduler/             # 定时任务调度
├── templates/            # 消息模板
├── config/              # 环境配置
└── types/               # 类型定义
```
