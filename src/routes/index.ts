import { Router, Request, Response } from 'express'

export function createRoutes(): Router {
  const router = Router()

  router.get('/health', (_req: Request, res: Response) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() })
  })

  return router
}
