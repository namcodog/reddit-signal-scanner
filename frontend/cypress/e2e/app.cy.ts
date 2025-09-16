describe('Reddit Signal Scanner E2E', () => {
  it('loads homepage', () => {
    cy.visit('/');
    cy.contains('Reddit Signal Scanner');
  });
});