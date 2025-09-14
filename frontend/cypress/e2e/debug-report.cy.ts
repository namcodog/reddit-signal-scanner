/**
 * DEBUG TEST: 调试报告页面加载问题
 */

describe('Debug Report Page', () => {
  const validTaskId = 'test-analysis-123';

  beforeEach(() => {
    // 模拟所有可能的API
    cy.intercept('GET', `/api/tasks/${validTaskId}/status`, {
      statusCode: 200,
      body: { status: 'completed', progress: 100 }
    });
    
    cy.intercept('GET', `/api/v1/reports/${validTaskId}*`, {
      statusCode: 200,
      body: {
        success: true,
        data: {
          task_id: validTaskId,
          status: 'completed',
          query: '测试产品描述',
          generated_at: new Date().toISOString(),
          total_posts: 1500,
          total_comments: 3200,
          analysis_duration: 125,
          data_freshness: '最新'
        }
      }
    });
    
    cy.intercept('POST', `/api/v1/reports/${validTaskId}/view`, {
      statusCode: 200,
      body: { success: true }
    });
    
    cy.on('uncaught:exception', () => false);
  });

  it('should debug what is actually loaded', () => {
    cy.visit(`/report/${validTaskId}`);
    
    // 等待页面加载
    cy.wait(3000);
    
    // 检查页面标题和URL
    cy.url().then((url) => {
      cy.log('Current URL:', url);
    });
    
    cy.title().then((title) => {
      cy.log('Page title:', title);
    });
    
    // 获取页面的所有data-testid元素
    cy.get('[data-testid]').then(($elements) => {
      cy.log(`Found ${$elements.length} elements with data-testid`);
      $elements.each((index, element) => {
        cy.log(`Element ${index}: ${element.getAttribute('data-testid')}`);
      });
    });
    
    // 获取页面HTML内容进行调试
    cy.get('body').then(($body) => {
      const html = $body.html();
      cy.log('Page HTML length:', html.length);
      
      // 查找关键元素
      if (html.includes('data-testid="report-page"')) {
        cy.log('Found report-page element');
      } else {
        cy.log('❌ No report-page element found');
        
        // 查看是否有其他关键内容
        if (html.includes('验证中')) {
          cy.log('Found "验证中" - still loading');
        }
        if (html.includes('Navigate')) {
          cy.log('Found Navigate - being redirected');
        }
        if (html.includes('报告页面')) {
          cy.log('Found "报告页面" text');
        }
        if (html.includes('Loading') || html.includes('loading')) {
          cy.log('Found loading state');
        }
        
        // 输出HTML片段
        const snippet = html.substring(0, 500) + '...';
        cy.log('HTML snippet:', snippet);
      }
    });
    
    // 检查是否有错误页面
    cy.get('body').should('exist');
  });
});