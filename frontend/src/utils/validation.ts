/**
 * 输入验证工具 - 遵循Linus简洁原则
 * 单一职责：只负责输入验证，不处理加密和网络请求
 */

export interface ValidationResult {
  valid: boolean;
  error?: string;
  sanitized?: string;
}

/**
 * 输入验证器 - 专注单一功能
 */
export class InputValidator {
  /**
   * HTML字符转义 - 防XSS
   */
  static escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 产品描述验证 - 核心验证逻辑
   */
  static validateProductDescription(input: string): ValidationResult {
    // 基础长度检查
    if (!input || input.trim().length === 0) {
      return { valid: false, error: '产品描述不能为空' };
    }

    if (input.length < 10) {
      return { valid: false, error: '产品描述至少需要10个字符' };
    }

    if (input.length > 2000) {
      return { valid: false, error: '产品描述不能超过2000个字符' };
    }

    // 安全检查 - 简化版本，只检查最危险的脚本
    if (/<script\b|javascript:|on\w+\s*=/i.test(input)) {
      return { valid: false, error: '输入内容包含不安全的代码' };
    }

    // 内容质量检查
    const cleanInput = input.trim();
    if (cleanInput.length < 8) {
      return { valid: false, error: '请提供更详细的产品描述' };
    }

    return {
      valid: true,
      sanitized: this.escapeHtml(cleanInput),
    };
  }
}

export default InputValidator;
