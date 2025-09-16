/// <reference types="cypress" />

const TASK_ID = '33333333-3333-4333-8bbb-333333333333'

describe('SSE 恢复：短暂错误后仍使用 SSE 完成', () => {
  it('SSE onerror 后重新连接 onopen，再通过 message 完成', () => {
    // 拦截报告接口，确保最终跳转稳定
    cy.intercept('GET', `/api/v1/report/${TASK_ID}`, {
      statusCode: 200,
      body: { title: 'Report OK', sections: [] },
    }).as('report')

    // 任务守卫路径：返回 200 以通过 ProtectedRoute
    cy.intercept('GET', `/api/tasks/${TASK_ID}/status`, { statusCode: 200, body: {} }).as('guard')

    // 使用可控 stub：手动触发 error -> 等待 -> open -> message
    cy.stubEventSource()
    cy.clock()

    cy.visit(`/analysis/${TASK_ID}`)

    // 初始实例：触发错误，驱动重连
    cy.window().then((win: any) => {
      const es1 = (win as any).__lastEventSource
      expect(es1).to.exist
      es1._emit('error')
    })

    // 等待重连间隔（默认 2000ms）
    cy.tick(2000)

    // 第二个实例：成功打开并推进到完成
    cy.window().then((win: any) => {
      const es2 = (win as any).__lastEventSource
      expect(es2).to.exist
      es2._emit('open')
      es2._emit('message', {
        status: 'processing',
        progress: 50,
        current_step: 'intelligent-analysis',
        step_progress: 50,
        estimated_remaining_seconds: 60,
      })
      es2._emit('message', { status: 'completed', progress: 100 })
    })

    // 完成后跳转报告页
    cy.url({ timeout: 6000 }).should('include', `/report/${TASK_ID}`)
  })
})

