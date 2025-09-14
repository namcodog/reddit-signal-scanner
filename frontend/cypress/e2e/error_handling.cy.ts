/// <reference types="cypress" />

describe('错误处理：提交失败与无效任务ID', () => {
  it('提交分析失败时展示错误提示', () => {
    cy.intercept('POST', '/api/v1/analyze', {
      statusCode: 500,
      body: { message: 'Internal Error' },
    }).as('analyzeFailed')

    cy.visit('/')
    cy.get('[data-testid="product-description-input"]').type('Short but valid content 123')
    cy.get('[data-testid="submit-button"]').should('not.be.disabled').click()

    cy.get('[data-testid="error-message"]').should('be.visible')
  })

  it('无效任务ID重定向到首页', () => {
    const badId = 'not-a-valid-uuid'
    cy.intercept('GET', `/api/tasks/${badId}/status`, { statusCode: 404 }).as('guardBad')

    cy.visit(`/report/${badId}`)

    cy.location('pathname', { timeout: 4000 }).should('eq', '/')
  })
})

