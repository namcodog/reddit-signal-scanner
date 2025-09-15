/**
 * E2E Test: Submit Analysis Flow
 * 基于context7 Cypress最佳实践：测试独立性 + API优先 + 数据属性选择器
 * 
 * 测试场景：用户输入产品描述 → 提交分析 → 跳转到等待页面
 */

describe('Submit Analysis Flow', () => {
  beforeEach(() => {
    // 最佳实践：在beforeEach中设置干净状态，确保测试独立性
    cy.visit('/');
    
    // 验证页面加载完成
    cy.get('[data-testid="product-description-input"]', { timeout: 10000 })
      .should('be.visible');
  });

  it('should successfully submit analysis with valid input', () => {
    const testDescription = 'AI-powered productivity tools for remote teams. Users are struggling with manual task management and communication overhead in distributed work environments.';
    
    // 最佳实践：使用data-testid属性选择器
    cy.get('[data-testid="product-description-input"]')
      .should('be.empty')
      .type(testDescription);
    
    // 验证输入内容
    cy.get('[data-testid="product-description-input"]')
      .should('have.value', testDescription);
    
    // 验证字符计数显示 - 匹配实际格式 {count}/2000 字符
    cy.get('[data-testid="character-count"]')
      .should('contain', '字符');
    
    // 验证提交按钮可用
    cy.get('[data-testid="submit-button"]')
      .should('not.be.disabled')
      .should('contain', '开始 5 分钟分析');
    
    // 模拟API响应 - 匹配实际API端点
    cy.intercept('POST', '/api/v1/analyze', {
      fixture: 'analysis-response.json'
    }).as('submitAnalysis');
    
    // 提交分析
    cy.get('[data-testid="submit-button"]').click();
    
    // 验证API调用 - 匹配真实请求体格式
    cy.wait('@submitAnalysis').then((interception) => {
      expect(interception.request.body).to.have.property('product_description');
      expect(interception.request.body.product_description.trim()).to.equal(testDescription);
      expect(interception.request.body).to.have.property('timestamp');
    });
    
    // 验证跳转到等待页面
    cy.url().should('include', '/analysis/test-analysis-123');
    
    // 验证等待页面加载
    cy.get('[data-testid="waiting-page"]', { timeout: 10000 })
      .should('be.visible');
    
    // 验证任务ID显示
    cy.get('[data-testid="task-id"]')
      .should('contain', 'test-analysis-123');
  });

  it('should show validation error for empty input', () => {
    // 验证空输入时按钮被禁用
    cy.get('[data-testid="submit-button"]')
      .should('be.disabled');
    
    // 尝试强制点击禁用的按钮（不会真正提交）
    cy.get('[data-testid="submit-button"]').click({ force: true });
    
    // 验证仍在输入页面（没有跳转）
    cy.url().should('equal', Cypress.config().baseUrl + '/');
  });

  it('should show validation error for input too short', () => {
    const shortDescription = 'Test';
    
    cy.get('[data-testid="product-description-input"]')
      .type(shortDescription);
    
    // 字符计数应显示字符数
    cy.get('[data-testid="character-count"]')
      .should('contain', '4/2000 字符');
    
    // 验证按钮被禁用（输入少于10个字符）
    cy.get('[data-testid="submit-button"]')
      .should('be.disabled');
    
    // 尝试强制提交短输入
    cy.get('[data-testid="submit-button"]').click({ force: true });
    
    // 验证仍在输入页面
    cy.url().should('equal', Cypress.config().baseUrl + '/');
  });

  it('should show validation error for input too long', () => {
    const longDescription = 'A'.repeat(2001); // 超过2000字符限制
    
    cy.get('[data-testid="product-description-input"]')
      .type(longDescription);
    
    // 验证字符计数显示 - 注意textarea的maxLength会阻止超出2000字符
    // 所以实际上最多只能输入2000字符
    cy.get('[data-testid="character-count"]')
      .should('contain', '2000/2000 字符');
    
    // 按钮应该可用（因为达到了2000字符的限制）
    cy.get('[data-testid="submit-button"]')
      .should('not.be.disabled');
  });

  it('should handle API submission error gracefully', () => {
    const validDescription = 'Valid product description for testing API error handling';
    
    // 模拟API错误 - 匹配实际API端点
    cy.intercept('POST', '/api/v1/analyze', {
      statusCode: 500,
      body: { error: 'Internal server error' }
    }).as('submitAnalysisError');
    
    cy.get('[data-testid="product-description-input"]')
      .type(validDescription);
    
    cy.get('[data-testid="submit-button"]').click();
    
    cy.wait('@submitAnalysisError');
    
    // 验证错误处理 - 会显示错误消息
    cy.get('[data-testid="error-message"]')
      .should('be.visible');
    
    // 验证按钮文本恢复 - 在错误状态下，按钮可能保持禁用状态
    cy.get('[data-testid="submit-button"]')
      .should('contain', '开始 5 分钟分析');
    
    // 验证仍在输入页面
    cy.url().should('equal', Cypress.config().baseUrl + '/');
  });

  it('should show loading state during submission', () => {
    const validDescription = 'Test product description for loading state verification';
    
    // 模拟慢速API响应 - 匹配实际API端点
    cy.intercept('POST', '/api/v1/analyze', {
      fixture: 'analysis-response.json',
      delay: 2000
    }).as('submitAnalysisSlow');
    
    cy.get('[data-testid="product-description-input"]')
      .type(validDescription);
    
    cy.get('[data-testid="submit-button"]').click();
    
    // 验证加载状态 - 按钮应该显示"正在提交..."且被禁用
    cy.get('[data-testid="submit-button"]')
      .should('be.disabled')
      .and('contain', '正在提交...');
    
    // 验证输入框在提交时禁用
    cy.get('[data-testid="product-description-input"]')
      .should('be.disabled');
    
    cy.wait('@submitAnalysisSlow');
    
    // 验证最终跳转
    cy.url().should('include', '/analysis/test-analysis-123');
  });
});