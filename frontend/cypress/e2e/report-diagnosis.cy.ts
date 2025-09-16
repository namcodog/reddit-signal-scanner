/**
 * 诊断测试：分析报告页面加载问题
 * 目标：不使用cy.wait()，记录所有网络请求，查看实际问题
 */

describe('Report Page Diagnosis', () => {
  const validTaskId = 'test-analysis-123';
  let networkRequests: any[] = [];

  beforeEach(() => {
    // 重置请求记录
    networkRequests = [];
    
    // 记录所有网络请求
    cy.intercept('**', (req) => {
      networkRequests.push({
        method: req.method,
        url: req.url,
        headers: req.headers,
        body: req.body
      });
      
      // 如果是我们期望的API，返回模拟响应
      if (req.url.includes(`/api/tasks/${validTaskId}/status`)) {
        req.reply({
          statusCode: 200,
          body: { status: 'completed', progress: 100 }
        });
        return;
      }
      
      if (req.url.includes(`/api/v1/reports/${validTaskId}`)) {
        req.reply({
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
              data_freshness: '最新',
              key_insights: [],
              sentiment_summary: {}
            }
          }
        });
        return;
      }
      
      // 其他请求继续正常处理
      req.continue();
    }).as('allRequests');
    
    // 忽略JavaScript错误
    cy.on('uncaught:exception', () => false);
  });

  it('should diagnose what happens when visiting report page', () => {
    // 访问报告页面
    cy.visit(`/report/${validTaskId}`);
    
    // 等待页面稳定
    cy.wait(5000);
    
    // 记录所有请求到控制台
    cy.then(() => {
      console.log('=== Network Requests ===');
      networkRequests.forEach((req, index) => {
        console.log(`${index + 1}. ${req.method} ${req.url}`);
      });
      console.log('=== End Requests ===');
    });
    
    // 检查页面URL
    cy.url().should('include', '/report/');
    
    // 检查页面内容
    cy.get('body').then(($body) => {
      const bodyText = $body.text();
      const bodyHtml = $body.html();
      
      console.log('=== Page Analysis ===');
      console.log('Body text length:', bodyText.length);
      console.log('Contains "验证中":', bodyText.includes('验证中'));
      console.log('Contains "报告页面":', bodyText.includes('报告页面'));
      console.log('Contains "输入页面":', bodyText.includes('输入页面'));
      console.log('Contains data-testid="report-page":', bodyHtml.includes('data-testid="report-page"'));
      console.log('Contains data-testid="product-description-input":', bodyHtml.includes('data-testid="product-description-input"'));
      
      // 输出HTML片段
      const snippet = bodyHtml.substring(0, 800);
      console.log('HTML snippet:', snippet);
      console.log('=== End Analysis ===');
    });
    
    // 最基本的验证 - 页面应该存在
    cy.get('body').should('exist');
    
    // 检查页面实际状态（不依赖元素查找）
    cy.get('body').then(($body) => {
      const bodyText = $body.text();
      const bodyHtml = $body.html();
      
      console.log('=== Page State Analysis ===');
      
      // 检查是否有testid元素
      const testidElements = $body.find('[data-testid]');
      console.log(`Found ${testidElements.length} elements with data-testid`);
      
      if (testidElements.length > 0) {
        testidElements.each((index, element) => {
          console.log(`Element ${index}: ${element.getAttribute('data-testid')}`);
        });
      }
      
      // 分析页面内容
      if (bodyText.includes('输入页面') || bodyHtml.includes('product-description-input')) {
        console.log('❌ 页面被重定向到了输入页面 - ProtectedRoute验证失败');
      } else if (bodyText.includes('报告页面') || bodyHtml.includes('report-page')) {
        console.log('✅ 找到了报告页面相关内容');
      } else if (bodyText.includes('验证中')) {
        console.log('⏳ 页面停留在验证状态 - API请求可能未完成');
      } else if (bodyText.includes('Not Found') || bodyText.includes('404')) {
        console.log('❌ 页面显示404错误');
      } else {
        console.log('❓ 页面状态未知');
        console.log('Page contains:', bodyText.substring(0, 200));
      }
      
      console.log('=== End State Analysis ===');
    });
    
    // 如果找不到testid元素，检查URL是否被改变
    cy.url().then((currentUrl) => {
      console.log('Current URL:', currentUrl);
      if (currentUrl.includes('/report/')) {
        console.log('✅ URL仍然是报告页面');
      } else {
        console.log('❌ URL已被重定向:', currentUrl);
      }
    });
  });

  it('should check if frontend app is running correctly', () => {
    // 访问首页检查应用是否正常
    cy.visit('/');
    
    cy.wait(3000);
    
    cy.get('body').should('exist');
    
    // 检查应用是否正确加载
    cy.get('body').then(($body) => {
      const bodyText = $body.text();
      console.log('=== Frontend App Status ===');
      console.log('Home page loaded, body text length:', bodyText.length);
      console.log('Contains input elements:', $body.find('input, textarea').length > 0);
      console.log('Contains React app:', bodyText.length > 100);
      
      if (bodyText.length < 100) {
        console.log('❌ 前端应用可能没有正确启动');
      } else {
        console.log('✅ 前端应用似乎在运行');
      }
    });
  });
});