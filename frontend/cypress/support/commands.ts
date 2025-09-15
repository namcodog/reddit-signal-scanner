/// <reference types="cypress" />

type TaskStatus = {
  task_id?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  message?: string
  current_step?: string
  step_progress?: number
  estimated_remaining_seconds?: number
  stats?: Record<string, number>
}

declare global {
  // 自定义命令类型补充
  namespace Cypress {
    interface Chainable {
      mockAnalyze(taskId: string): Chainable<void>
      mockTaskStatusSequence(taskId: string, seq: TaskStatus[]): Chainable<void>
      stubEventSource(): Chainable<void>
      stubEventSourceAutoError(times?: number): Chainable<void>
      emitSSE(data: TaskStatus): Chainable<void>
    }
  }
}

// 拦截提交分析接口
Cypress.Commands.add('mockAnalyze', (taskId: string) => {
  cy.intercept('POST', '/api/v1/analyze', {
    statusCode: 200,
    body: { task_id: taskId },
  }).as('analyze')
})

// 拦截任务状态接口，按序列返回（兼容两种路径）
Cypress.Commands.add('mockTaskStatusSequence', (taskId: string, seq: TaskStatus[]) => {
  let idx = 0
  const replyNext = (req: Cypress.Interception) => {
    const i = Math.min(idx, seq.length - 1)
    const body = { task_id: taskId, ...seq[i] }
    idx += 1
    req.reply({ statusCode: 200, body })
  }

  cy.intercept('GET', `/api/v1/tasks/${taskId}/status`, replyNext).as('statusV1')
  cy.intercept('GET', `/api/tasks/${taskId}/status`, replyNext).as('statusLegacy')
})

// 简单的 EventSource stub（手动触发事件）
Cypress.Commands.add('stubEventSource', () => {
  cy.window().then((win: any) => {
    class FakeES {
      url: string
      onopen?: () => void
      onmessage?: (ev: MessageEvent) => void
      onerror?: (ev: Event) => void
      private listeners: Record<string, Function[]> = {}
      constructor(url: string) {
        this.url = url
        ;(win as any).__lastEventSource = this
      }
      addEventListener(type: string, cb: Function) {
        this.listeners[type] = this.listeners[type] || []
        this.listeners[type].push(cb)
      }
      close() {}
      _emit(type: string, payload?: any) {
        if (type === 'open' && this.onopen) this.onopen()
        if (type === 'message' && this.onmessage)
          this.onmessage({ data: JSON.stringify(payload) } as MessageEvent)
        if (type === 'error' && this.onerror) this.onerror(new Event('error'))
        ;(this.listeners[type] || []).forEach((fn) => fn({ data: JSON.stringify(payload) }))
      }
    }
    ;(win as any).EventSource = function (url: string) {
      return new (FakeES as any)(url)
    }
  })
})

// 自动错误的 EventSource（用于触发降级到轮询）。times 指定连续错误次数
Cypress.Commands.add('stubEventSourceAutoError', (times: number = 3) => {
  cy.window().then((win: any) => {
    let constructed = 0
    class AutoErrorES {
      url: string
      onopen?: () => void
      onmessage?: (ev: MessageEvent) => void
      onerror?: (ev: Event) => void
      constructor(url: string) {
        this.url = url
        constructed += 1
        ;(win as any).__lastEventSource = this
        // 下一tick自动触发错误，驱动重连
        setTimeout(() => {
          if (constructed <= times) {
            this.onerror && this.onerror(new Event('error'))
          }
        }, 0)
      }
      addEventListener() {}
      close() {}
    }
    ;(win as any).EventSource = function (url: string) {
      return new (AutoErrorES as any)(url)
    }
  })
})

// 便捷：向上一次 EventSource 发送 SSE 消息
Cypress.Commands.add('emitSSE', (data: TaskStatus) => {
  cy.window().then((win: any) => {
    const es = (win as any).__lastEventSource
    if (es && es._emit) {
      es._emit('message', data)
    } else if (es && es.onmessage) {
      es.onmessage({ data: JSON.stringify(data) })
    } else {
      throw new Error('No stubbed EventSource instance to emit message')
    }
  })
})

export {}

