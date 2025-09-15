"""验收测试示例 - 首次用户E2E测试

展示验收测试的最佳实践：
1. 从用户视角测试
2. 使用真实浏览器（Cypress/Playwright）
3. 验证业务价值
4. 跨浏览器兼容性
"""

import pytest
from typing import Dict, Any
from playwright.async_api import async_playwright, Page, BrowserContext

from tests.fixtures.base_fixtures import TestIsolation, performance_timer


@TestIsolation.acceptance_test
class TestFirstTimeUserE2E:
    """首次用户端到端验收测试"""
    
    @pytest.fixture
    async def browser_context(self):
        """创建浏览器上下文"""
        async with async_playwright() as p:
            # 可以测试多种浏览器
            browser = await p.chromium.launch(
                headless=True,  # CI环境下无头模式
                slow_mo=50  # 慢速执行，便于观察
            )
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="zh-CN",
                timezone_id="Asia/Shanghai"
            )
            
            # 设置默认超时
            context.set_default_timeout(30000)  # 30秒
            
            yield context
            
            await context.close()
            await browser.close()
            
    @pytest.fixture
    async def page(self, browser_context: BrowserContext) -> Page:
        """创建新页面"""
        page = await browser_context.new_page()
        
        # 监听控制台错误
        page.on("console", lambda msg: print(f"Console {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: pytest.fail(f"页面错误: {err}"))
        
        yield page
        
        await page.close()
        
    async def test_complete_first_time_user_journey(self, page: Page, performance_timer):
        """测试首次用户完整旅程"""
        performance_timer.start()
        
        # 1. 访问首页
        await page.goto("http://localhost:3000")
        await page.wait_for_load_state("networkidle")
        performance_timer.checkpoint("homepage_loaded")
        
        # 验证首页元素
        assert await page.is_visible("text=Reddit Signal Scanner")
        assert await page.is_visible("text=发现商业机会")
        
        # 截图保存（用于视觉回归测试）
        await page.screenshot(path="screenshots/homepage.png")
        
        # 2. 点击"开始使用"
        await page.click("button:has-text('开始使用')")
        await page.wait_for_url("**/register")
        performance_timer.checkpoint("registration_page")
        
        # 3. 填写注册表单
        await self._fill_registration_form(page, {
            "email": "e2e_test@example.com",
            "password": "SecurePass123!",
            "confirmPassword": "SecurePass123!",
            "agreeTerms": True
        })
        
        # 4. 提交注册
        await page.click("button:has-text('注册')")
        await page.wait_for_url("**/dashboard")
        performance_timer.checkpoint("registration_complete")
        
        # 5. 首次使用引导
        # 验证引导提示出现
        await page.wait_for_selector(".onboarding-tooltip")
        
        # 跳过引导（或完成引导流程）
        if await page.is_visible("button:has-text('跳过引导')"):
            await page.click("button:has-text('跳过引导')")
            
        # 6. 创建第一个分析任务
        await page.click("button:has-text('新建分析')")
        await page.wait_for_selector(".analysis-form")
        
        # 填写分析表单
        await page.fill("input[name='keywords']", "startup, entrepreneur, business idea")
        await page.select_option("select[name='limit']", "50")
        
        # 选择subreddit
        await page.click(".subreddit-selector")
        await page.click("text=r/entrepreneur")
        await page.click("text=r/startups")
        
        # 提交分析
        await page.click("button:has-text('开始分析')")
        performance_timer.checkpoint("analysis_submitted")
        
        # 7. 等待分析完成
        # 显示进度条
        await page.wait_for_selector(".progress-bar")
        
        # 等待完成（最多2分钟）
        await page.wait_for_selector(
            "text=分析完成",
            timeout=120000  # 2分钟
        )
        performance_timer.checkpoint("analysis_complete")
        
        # 8. 查看分析结果
        await page.click("button:has-text('查看报告')")
        await page.wait_for_selector(".analysis-report")
        
        # 验证报告内容
        assert await page.is_visible(".pain-points-section")
        assert await page.is_visible(".opportunities-section")
        assert await page.is_visible(".competitors-section")
        
        # 验证至少有一些结果
        pain_points = await page.query_selector_all(".pain-point-item")
        assert len(pain_points) > 0
        
        opportunities = await page.query_selector_all(".opportunity-item")
        assert len(opportunities) > 0
        
        # 9. 导出报告
        await page.click("button:has-text('导出报告')")
        await page.click("text=PDF格式")
        
        # 等待下载
        download = await page.wait_for_event("download")
        assert "report" in download.suggested_filename
        performance_timer.checkpoint("report_downloaded")
        
        # 10. 返回仪表板
        await page.click("a:has-text('仪表板')")
        await page.wait_for_url("**/dashboard")
        
        # 验证任务出现在历史记录中
        assert await page.is_visible(".task-history")
        history_items = await page.query_selector_all(".history-item")
        assert len(history_items) >= 1
        
        performance_timer.stop()
        
        # 验证整体性能
        assert performance_timer.duration < 180  # 3分钟内完成
        
    async def test_mobile_responsive_journey(self, browser_context: BrowserContext):
        """测试移动端响应式体验"""
        # 创建移动端视口
        mobile_page = await browser_context.new_page()
        await mobile_page.set_viewport_size({"width": 375, "height": 667})  # iPhone SE
        
        # 访问首页
        await mobile_page.goto("http://localhost:3000")
        
        # 验证移动端导航
        # 汉堡菜单应该可见
        assert await mobile_page.is_visible(".mobile-menu-button")
        
        # 点击汉堡菜单
        await mobile_page.click(".mobile-menu-button")
        await mobile_page.wait_for_selector(".mobile-menu-overlay")
        
        # 验证菜单项
        assert await mobile_page.is_visible("text=首页")
        assert await mobile_page.is_visible("text=功能")
        assert await mobile_page.is_visible("text=定价")
        
        # 测试触摸滑动
        await mobile_page.touch_screen.swipe(
            start_x=200, start_y=300,
            end_x=200, end_y=100,
            steps=10
        )
        
        await mobile_page.close()
        
    async def test_accessibility_compliance(self, page: Page):
        """测试可访问性合规"""
        await page.goto("http://localhost:3000")
        
        # 使用axe-core进行可访问性测试
        await page.add_script_tag(
            url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.7.0/axe.min.js"
        )
        
        # 运行可访问性检查
        results = await page.evaluate("""
            async () => {
                return await axe.run();
            }
        """)
        
        violations = results.get("violations", [])
        
        # 不应该有严重的可访问性问题
        critical_violations = [v for v in violations if v["impact"] in ["critical", "serious"]]
        
        if critical_violations:
            violation_summary = "\n".join([
                f"- {v['description']}: {v['help']}"
                for v in critical_violations
            ])
            pytest.fail(f"发现严重的可访问性问题:\n{violation_summary}")
            
    async def test_error_handling_user_experience(self, page: Page):
        """测试错误处理的用户体验"""
        await page.goto("http://localhost:3000")
        
        # 1. 测试网络错误处理
        # 模拟网络中断
        await page.route("**/api/**", lambda route: route.abort())
        
        # 尝试提交表单
        await page.click("button:has-text('开始使用')")
        
        # 应该显示友好的错误提示
        await page.wait_for_selector(".error-message")
        error_text = await page.text_content(".error-message")
        assert "网络连接" in error_text or "Network" in error_text
        
        # 恢复网络
        await page.unroute("**/api/**")
        
        # 2. 测试表单验证错误
        await page.reload()
        await page.click("button:has-text('开始使用')")
        
        # 提交空表单
        await page.click("button:has-text('注册')")
        
        # 验证错误提示
        assert await page.is_visible("text=请输入邮箱")
        assert await page.is_visible("text=请输入密码")
        
    @pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
    async def test_cross_browser_compatibility(self, browser_name: str):
        """测试跨浏览器兼容性"""
        async with async_playwright() as p:
            # 获取对应的浏览器
            browser_type = getattr(p, browser_name)
            browser = await browser_type.launch(headless=True)
            
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # 基本功能测试
                await page.goto("http://localhost:3000")
                await page.wait_for_load_state("networkidle")
                
                # 验证关键元素
                assert await page.is_visible("text=Reddit Signal Scanner")
                
                # 测试交互
                await page.click("button:has-text('开始使用')")
                await page.wait_for_url("**/register")
                
                # 验证页面正确加载
                assert await page.is_visible("form")
                
            finally:
                await browser.close()
                
    # ==================== 辅助方法 ====================
    
    async def _fill_registration_form(self, page: Page, data: Dict[str, Any]):
        """填写注册表单"""
        await page.fill("input[name='email']", data["email"])
        await page.fill("input[name='password']", data["password"])
        await page.fill("input[name='confirmPassword']", data["confirmPassword"])
        
        if data.get("agreeTerms"):
            await page.check("input[name='agreeTerms']")
            
    async def _wait_for_analysis_complete(self, page: Page, timeout: int = 120):
        """等待分析完成"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查进度
            progress_text = await page.text_content(".progress-percentage")
            if progress_text and "100%" in progress_text:
                return True
                
            # 检查完成状态
            if await page.is_visible("text=分析完成"):
                return True
                
            await page.wait_for_timeout(2000)  # 等待2秒
            
        return False
        
    async def _capture_performance_metrics(self, page: Page) -> Dict[str, Any]:
        """捕获性能指标"""
        metrics = await page.evaluate("""
            () => {
                const navigation = performance.getEntriesByType('navigation')[0];
                const paint = performance.getEntriesByType('paint');
                
                return {
                    domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
                    loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
                    firstPaint: paint.find(p => p.name === 'first-paint')?.startTime,
                    firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime
                };
            }
        """)
        
        return metrics