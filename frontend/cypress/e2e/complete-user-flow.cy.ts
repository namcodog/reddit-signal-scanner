/**
 * E2E Test: Complete User Flow
 * 基于context7 Cypress最佳实践：完整用户旅程测试
 * 
 * 测试场景：输入描述 → 提交分析 → 等待页面 → 查看报告（当前开发状态）
 * Context7原则：测试真实用户体验，不创建假功能
 */

describe('Complete User Flow', () => {
  const testDescription = 'AI-powered productivity tools for remote teams. Users are struggling with manual task management, communication overhead, and time tracking difficulties in distributed work environments.';
  const taskId = 'test-analysis-123';

  beforeEach(() => {
    // 最佳实践：在beforeEach中设置所有API模拟，确保测试独立性
    
    // 模拟分析提交API - 匹配实际API路径
    cy.intercept('POST', '/api/v1/analyze', {
      fixture: 'analysis-response.json'
    }).as('submitAnalysis');
    
    // 模拟任务状态API - 简化版本，直接返回完成状态
    cy.intercept('GET', `/api/v1/tasks/${taskId}/status`, {
      task_id: taskId,
      status: 'completed',
      progress: 100,
      step: 4,
      total_steps: 4,
      current_step_name: 'Analysis complete',
      message: 'Reddit analysis completed successfully',
      elapsed_time: '2m 15s',
      estimated_remaining: '0s',
      timestamp: new Date().toISOString()
    }).as('getTaskStatus');
    
    // 不需要模拟报告API，因为当前报告页面是静态的开发状态
  });

  it('should complete the entire user journey to development report page', () => {
    // === 第1步：输入页面 ===
    cy.visit('/');
    
    // 验证输入页面加载
    cy.get('[data-testid="product-description-input"]', { timeout: 10000 })
      .should('be.visible')
      .and('be.empty');
    
    cy.get('[data-testid="submit-button"]')
      .should('be.visible')
      .and('contain', '开始 5 分钟分析');
    
    // 输入产品描述
    cy.get('[data-testid="product-description-input"]')
      .type(testDescription);
    
    // 验证输入反馈 - 修复：匹配实际的字符计数格式
    cy.get('[data-testid="character-count"]')
      .should('contain', '字符');
    
    cy.get('[data-testid="submit-button"]')
      .should('not.be.disabled');
    
    // 提交分析
    cy.get('[data-testid="submit-button"]').click();
    
    // 验证API调用 - 修复：匹配实际请求体格式
    cy.wait('@submitAnalysis').then((interception) => {
      expect(interception.request.body).to.have.property('product_description');
      expect(interception.request.body.product_description.trim()).to.equal(testDescription);
      expect(interception.request.body).to.have.property('timestamp');
    });
    
    // === 第2步：等待页面 ===
    // 验证跳转到等待页面
    cy.url().should('include', `/analysis/${taskId}`);
    
    cy.get('[data-testid="waiting-page"]', { timeout: 10000 })
      .should('be.visible');
    
    // 验证任务信息显示
    cy.get('[data-testid="task-id"]')
      .should('contain', taskId);
    
    // 验证进度显示组件
    cy.get('[data-testid="progress-tracker"]')
      .should('be.visible');
    
    // 验证进度百分比
    cy.get('[data-testid="progress-percentage"]')
      .should('be.visible');
    
    // === 第3步：手动跳转到报告页面（当前无自动跳转） ===
    // 模拟用户手动导航到报告页面
    cy.visit(`/report/${taskId}`);
    
    // === 第4步：验证真实的开发状态报告页面 ===
    // 验证报告页面加载
    cy.get('[data-testid="report-page"]', { timeout: 10000 })
      .should('be.visible');
    
    // 验证任务ID显示
    cy.get('[data-testid="task-id"]')
      .should('contain', taskId);
    
    // Context7最佳实践：验证真实的报告页面内容而不是占位符
    cy.contains('分析报告').should('be.visible');
    cy.contains('任务ID').should('be.visible');
    
    // 验证报告页面的核心组件已加载
    cy.get('.container').should('be.visible');
    cy.get('h1').should('contain', '分析报告');
    
    // === 验证完整流程的数据一致性 ===
    // 确认任务ID在整个流程中保持一致
    cy.get('[data-testid="task-id"]')
      .should('contain', taskId);
    
    // 验证报告内容（不依赖特定图标）
    cy.get('[data-testid="task-id"]').should('be.visible');
  });

  it('should handle interruptions and allow manual navigation between pages', () => {
    // 测试用户中途离开并通过URL直接访问的场景
    cy.visit('/');
    
    // 输入描述但不提交
    cy.get('[data-testid="product-description-input"]')
      .type(testDescription);
    
    // 直接访问等待页面
    cy.visit(`/analysis/${taskId}`);
    
    // 应该能正常显示等待页面
    cy.get('[data-testid="waiting-page"]')
      .should('be.visible');
    
    // 直接访问报告页面
    cy.visit(`/report/${taskId}`);
    
    // 应该能正常显示开发状态报告
    cy.get('[data-testid="report-page"]')
      .should('be.visible');
    
    // Context7最佳实践：验证真实功能
    cy.contains('分析报告').should('be.visible');
  });

  it('should handle network errors gracefully during the flow', () => {
    cy.visit('/');
    
    // 模拟提交API错误 - 匹配实际API路径
    cy.intercept('POST', '/api/v1/analyze', {
      statusCode: 500,
      body: { error: 'Server error' }
    }).as('submitAnalysisError');
    
    cy.get('[data-testid="product-description-input"]')
      .type(testDescription);
    
    cy.get('[data-testid="submit-button"]').click();
    
    cy.wait('@submitAnalysisError');
    
    // 等待错误状态稳定
    cy.wait(1000);
    
    // 验证错误处理 - 修复：匹配实际的错误消息
    cy.get('[data-testid="error-message"]')
      .should('be.visible');
    
    // 验证错误状态显示
    cy.get('[data-testid="submit-button"]')
      .should('be.visible')
      .and('contain', '开始 5 分钟分析');
    
    // 恢复正常API并重试 - 匹配实际API路径
    cy.intercept('POST', '/api/v1/analyze', {
      fixture: 'analysis-response.json'
    }).as('submitAnalysisRetry');
    
    // 重新输入内容以激活按钮
    cy.get('[data-testid="product-description-input"]')
      .clear()
      .type(testDescription);
      
    // 等待按钮状态更新
    cy.get('[data-testid="submit-button"]')
      .should('not.be.disabled');
      
    cy.get('[data-testid="submit-button"]').click();
    
    cy.wait('@submitAnalysisRetry');
    
    // 验证重试成功，到达等待页面
    cy.url().should('include', `/analysis/${taskId}`);
    cy.get('[data-testid="waiting-page"]').should('be.visible');
  });

  it('should maintain consistent UI theme across all pages', () => {
    // 验证输入页面主题
    cy.visit('/');
    cy.get('.min-h-screen').should('have.class', 'bg-gradient-to-br');
    cy.contains('Reddit Signal Scanner').should('be.visible');
    
    // 提交并到达等待页面
    cy.get('[data-testid="product-description-input"]').type(testDescription);
    cy.get('[data-testid="submit-button"]').click();
    cy.wait('@submitAnalysis');
    
    // 验证等待页面主题一致性
    cy.get('[data-testid="waiting-page"]')
      .should('have.class', 'min-h-screen')
      .and('have.class', 'bg-gradient-to-br');
    
    // 到达报告页面
    cy.visit(`/report/${taskId}`);
    
    // 验证报告页面主题一致性 - 修复：匹配实际的CSS类名
    cy.get('[data-testid="report-page"]')
      .should('have.class', 'min-h-screen')
      .and('have.class', 'bg-gradient-to-br');
    
    // 验证所有页面都有合适的内容区域 - 修复：匹配实际的容器类名
    cy.get('.container, .max-w-7xl').should('be.visible');
  });

  it('should support browser back/forward navigation', () => {
    // 完成提交流程
    cy.visit('/');
    cy.get('[data-testid="product-description-input"]').type(testDescription);
    cy.get('[data-testid="submit-button"]').click();
    cy.wait('@submitAnalysis');
    
    // 到达等待页面
    cy.url().should('include', `/analysis/${taskId}`);
    
    // 手动导航到报告页面
    cy.visit(`/report/${taskId}`);
    cy.get('[data-testid="report-page"]').should('be.visible');
    
    // 使用浏览器后退按钮
    cy.go('back');
    cy.get('[data-testid="waiting-page"]').should('be.visible');
    
    // 使用浏览器前进按钮
    cy.go('forward');
    cy.get('[data-testid="report-page"]').should('be.visible');
    
    // 验证数据保持一致
    cy.get('[data-testid="task-id"]').should('contain', taskId);
  });

  it('should handle different viewport sizes throughout the flow', () => {
    // 测试移动端完整流程
    cy.viewport(375, 667);
    
    cy.visit('/');
    cy.get('[data-testid="product-description-input"]')
      .should('be.visible')
      .type(testDescription);
    
    cy.get('[data-testid="submit-button"]').click();
    cy.wait('@submitAnalysis');
    
    cy.get('[data-testid="waiting-page"]').should('be.visible');
    
    cy.visit(`/report/${taskId}`);
    cy.get('[data-testid="report-page"]').should('be.visible');
    cy.contains('分析报告').should('be.visible');
    
    // 切换到桌面端
    cy.viewport(1200, 800);
    cy.get('[data-testid="report-page"]').should('be.visible');
    cy.contains('分析报告').should('be.visible');
  });
});