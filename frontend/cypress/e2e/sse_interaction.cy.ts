/// <reference types="cypress" />

const TASK_ID = '22222222-2222-4222-8aaa-222222222222'

describe('SSE 交互：失败后降级到轮询', () => {
  it('SSE 连续错误触发降级，轮询推进到完成', () => {
    // 任务校验与轮询状态序列（pending -> processing -> completed）
    cy.mockTaskStatusSequence(TASK_ID, [
      { status: 'pending', progress: 0 },
      { status: 'processing', progress: 60, current_step: 'intelligent-analysis', step_progress: 60 },
      { status: 'completed', progress: 100 },
    ])

    // ProtectedRoute 也会检查 legacy 路径，这里已经由命令覆盖

    // SSE 自动错误 stub（3 次），配合时钟快进，迅速触发降级
    cy.stubEventSourceAutoError(3)
    cy.clock()

    // 报告接口拦截，避免跳转后加载报错
    cy.intercept('GET', `/api/v1/report/${TASK_ID}`, {
      statusCode: 200,
      body: { title: 'Report OK', sections: [] },
    }).as('report')

    cy.visit(`/analysis/${TASK_ID}`)

    // 快进3次重连间隔（每次默认2000ms）
    cy.tick(2000)
    cy.tick(2000)
    cy.tick(2000)

    // 断言降级文案（显示轮询）与进度推进
    cy.contains('实时连接 (轮询)').should('exist')
    cy.get('[data-testid="progress-percentage"]').should('contain.text', '%')

    // 最终跳转报告页
    cy.url({ timeout: 6000 }).should('include', `/report/${TASK_ID}`)
  })
})
