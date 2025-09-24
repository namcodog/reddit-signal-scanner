/// <reference types="cypress" />

describe('Admin actions smoke', () => {
  it('communities approve action triggers API and shows trace id', () => {
    cy.intercept('GET', '/api/v1/admin/communities/summary*', {
      statusCode: 200,
      body: {
        code: 0,
        data: { total: 1, items: [{ community: 'r/test', c_score: 80, status_color: 'green', hit_7d: 42 }] },
        trace_id: 'tid-mock',
      },
    }).as('getCommunities')

    cy.intercept('POST', '/api/v1/admin/decisions/community', {
      statusCode: 200,
      body: { code: 0, data: { event_id: 'eid' }, trace_id: 'tid-approve' },
    }).as('postDecision')

    cy.visit('/admin/communities')
    cy.wait('@getCommunities')
    cy.contains('r/test')
    // 手动移除禁用，或在真实环境下先登录解锁
    cy.contains('通过').then($btn => $btn.prop('disabled', false))
    cy.contains('通过').click()
    cy.wait('@postDecision')
  })
})
