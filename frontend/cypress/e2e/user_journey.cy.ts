/// <reference types="cypress" />

const TASK_ID = '11111111-1111-4111-8111-111111111111'

describe('用户旅程：输入 -> 分析 -> 报告', () => {
  it('完成完整流程（SSE驱动，最终跳转报告页）', () => {
    // 拦截提交与任务状态验证
    cy.mockAnalyze(TASK_ID)
    // ProtectedRoute 会调用 legacy 路径校验一次，这里返回 200 即可
    cy.intercept('GET', `/api/tasks/${TASK_ID}/status`, { statusCode: 200, body: {} }).as('guard')

    // SSE 使用：stub 并手动推送消息
    cy.stubEventSource()

    // 报告接口拦截，避免页面加载报错
    cy.intercept('GET', `/api/v1/report/${TASK_ID}`, {
      statusCode: 200,
      body: { title: 'Report OK', sections: [] },
    }).as('report')

    cy.visit('/')

    // 填写产品描述
    const text = 'An AI note tool that organizes ideas and generates knowledge graphs.'
    cy.get('[data-testid="product-description-input"]').type(text)

    // 按钮可用后提交
    cy.get('[data-testid="submit-button"]').should('not.be.disabled').click()

    // 导航到 /analysis/:taskId
    cy.url().should('include', `/analysis/${TASK_ID}`)

    // 触发 SSE 打开与进度推进
    cy.window().then((win: any) => {
      const es = (win as any).__lastEventSource
      expect(es).to.exist
      es._emit('open')
    })

    // 推送处理中
    cy.emitSSE({
      status: 'processing',
      progress: 20,
      current_step: 'data-collection',
      step_progress: 40,
      estimated_remaining_seconds: 120,
      stats: { communities_found: 12, posts_analyzed: 200, insights_generated: 3 },
    })

    cy.get('[data-testid="progress-tracker"]').should('be.visible')
    cy.get('[data-testid="progress-percentage"]').should('contain.text', '%')

    // 推送完成
    cy.emitSSE({ status: 'completed', progress: 100 })

    // 完成后会2秒跳转报告页
    cy.url({ timeout: 6000 }).should('include', `/report/${TASK_ID}`)
  })
})
