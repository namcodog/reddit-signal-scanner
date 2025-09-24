/// <reference types="cypress" />

describe('Admin analysis actions smoke', () => {
  it('rates a task and updates trace id', () => {
    cy.intercept('GET', '/api/v1/admin/analysis/summary*', {
      statusCode: 200,
      body: {
        code: 0,
        data: { total: 1, items: [{ task_id: 'tsk1', a_score: 78, coverage: 0.8, relevance: 0.7, median_days: 3, dup_ratio: 0.1, spam_ratio: 0.06, diversity: 0.6, must: { coverage_ok: true, freshness_ok: true, relevance_ok: true, dup_ok: true, spam_ok: true, safety_ok: true } }] },
        trace_id: 'tid-mock',
      },
    }).as('getSummary')

    cy.intercept('POST', '/api/v1/admin/feedback/analysis', {
      statusCode: 200,
      body: { code: 0, data: { event_id: 'eid' }, trace_id: 'tid-rate' },
    }).as('postFeedback')

    cy.visit('/admin/analysis')
    cy.wait('@getSummary')
    cy.contains('tsk1')
    cy.contains('满意').then($btn => $btn.prop('disabled', false))
    cy.contains('满意').click()
    cy.wait('@postFeedback')
  })
})

