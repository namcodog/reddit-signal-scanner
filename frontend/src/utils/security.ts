import logger from '@/utils/logger';

/**
 * 安全工具类 - 消灭安全技术债务
 * 基于 Linus 安全第一原则：Never trust user input
 *
 * 解决问题：
 * 1. XSS防护 - HTML转义
 * 2. 输入验证 - 长度和内容检查
 * 3. 请求频率限制 - 防止滥用
 * 4. CSRF防护 - 请求头验证
 */

// 输入验证结果接口
export interface ValidationResult {
  valid: boolean;
  error?: string;
  sanitized?: string;
}

// 频率限制存储 (临时用内存，生产环境用Redis)
const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

/**
 * 安全工具类 - 集中处理所有安全相关功能
 */
export class SecurityUtils {
  // XSS防护 - HTML转义
  static escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // 反转义HTML (用于显示)
  static unescapeHtml(html: string): string {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || '';
  }

  // 产品描述验证 - 防止恶意输入
  static validateProductDescription(input: string): ValidationResult {
    // 长度检查
    if (!input || input.trim().length === 0) {
      return {
        valid: false,
        error: '产品描述不能为空',
      };
    }

    if (input.length < 10) {
      return {
        valid: false,
        error: '产品描述至少需要10个字符',
      };
    }

    if (input.length > 2000) {
      return {
        valid: false,
        error: '产品描述不能超过2000个字符',
      };
    }

    // 恶意脚本检查
    const dangerousPatterns = [
      /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
      /javascript:/gi,
      /on\w+\s*=/gi,
      /<iframe\b/gi,
      /<object\b/gi,
      /<embed\b/gi,
    ];

    for (const pattern of dangerousPatterns) {
      if (pattern.test(input)) {
        return {
          valid: false,
          error: '输入内容包含不安全的代码，请重新输入',
        };
      }
    }

    // 内容质量检查 - 支持中英文混合
    const cleanInput = input.trim();
    // 对于中文，按字符长度检查；对于英文，按单词数检查
    const hasChineseChars = /[\u4e00-\u9fff]/.test(cleanInput);

    if (hasChineseChars) {
      // 中文内容：至少8个汉字才算有意义
      if (cleanInput.length < 8) {
        return {
          valid: false,
          error: '产品描述内容过于简单，请提供更详细的描述',
        };
      }
    } else {
      // 英文内容：至少3个单词
      const wordCount = cleanInput.split(/\s+/).length;
      if (wordCount < 3) {
        return {
          valid: false,
          error: '产品描述应该包含至少3个有意义的词汇',
        };
      }
    }

    // 输入清理并返回
    const sanitized = this.escapeHtml(input.trim());

    return {
      valid: true,
      sanitized,
    };
  }

  // 请求频率限制 - 防止API滥用
  static checkRateLimit(
    key: string,
    maxRequests: number = 10,
    timeWindow: number = 60000 // 1分钟
  ): boolean {
    const now = Date.now();
    const record = rateLimitStore.get(key);

    if (!record || now > record.resetTime) {
      // 重置或创建新记录
      rateLimitStore.set(key, {
        count: 1,
        resetTime: now + timeWindow,
      });
      return true;
    }

    if (record.count >= maxRequests) {
      return false; // 超过限制
    }

    record.count++;
    return true;
  }

  // 获取客户端指纹 - 用于频率限制
  static getClientFingerprint(): string {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx!.textBaseline = 'top';
    ctx!.font = '14px Arial';
    ctx!.fillText('Browser fingerprint', 2, 2);

    const fingerprint = [
      navigator.userAgent,
      navigator.language,
      screen.width + 'x' + screen.height,
      new Date().getTimezoneOffset(),
      canvas.toDataURL(),
    ].join('|');

    // 简单hash
    let hash = 0;
    for (let i = 0; i < fingerprint.length; i++) {
      const char = fingerprint.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // 转换为32位整数
    }

    return Math.abs(hash).toString(16);
  }

  // 生成CSRF Token
  static generateCSRFToken(): string {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join(
      ''
    );
  }

  // 验证输入是否为有效的任务ID
  static validateTaskId(taskId: string): boolean {
    // UUID v4格式验证
    const uuidRegex =
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(taskId);
  }

  // 清理URL参数 - 防止XSS通过URL注入
  static sanitizeUrlParam(param: string): string {
    return param.replace(/[<>'"&]/g, '');
  }

  // 安全的JSON解析
  static safeJsonParse<T>(json: string, fallback: T): T {
    try {
      return JSON.parse(json);
    } catch {
      return fallback;
    }
  }
}

/**
 * 安全的fetch封装 - 替代原始fetch
 * 自动添加安全头部，处理CSRF保护
 */
export const secureApiFetch = async (
  url: string,
  options: RequestInit = {}
): Promise<Response> => {
  const clientFingerprint = SecurityUtils.getClientFingerprint();

  // 检查频率限制
  if (!SecurityUtils.checkRateLimit(clientFingerprint, 20, 60000)) {
    throw new Error('请求过于频繁，请稍后再试');
  }

  // 默认安全headers
  const secureHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest', // CSRF防护
    'X-Client-Fingerprint': clientFingerprint,
    ...options.headers,
  };

  // 添加CSRF token (如果是POST/PUT/DELETE请求)
  if (
    options.method &&
    ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method.toUpperCase())
  ) {
    const csrfToken =
      sessionStorage.getItem('csrf_token') || SecurityUtils.generateCSRFToken();
    sessionStorage.setItem('csrf_token', csrfToken);
    (secureHeaders as Record<string, string>)['X-CSRF-Token'] = csrfToken;
  }

  const secureOptions: RequestInit = {
    ...options,
    headers: secureHeaders,
    credentials: 'same-origin', // 安全的cookie策略
  };

  try {
    const response = await fetch(url, secureOptions);

    // 检查响应安全性
    if (!response.ok) {
      // 详细的错误处理
      let errorMessage = `HTTP ${response.status}`;

      try {
        const errorData = await response.json();
        errorMessage = errorData.message || errorMessage;
      } catch {
        // JSON解析失败，使用默认错误消息
      }

      throw new Error(errorMessage);
    }

    return response;
  } catch (error) {
    // 网络错误分类处理
    if (error instanceof TypeError) {
      throw new Error('网络连接失败，请检查网络设置');
    }

    throw error;
  }
};

/**
 * 安全的localStorage包装 - 加密存储敏感数据
 */
export class SecureStorage {
  private static readonly SECRET_KEY = 'reddit_scanner_key';

  // 简单的XOR加密 (生产环境使用AES)
  private static encrypt(text: string): string {
    const key = this.SECRET_KEY;
    let result = '';

    for (let i = 0; i < text.length; i++) {
      const charCode = text.charCodeAt(i) ^ key.charCodeAt(i % key.length);
      result += String.fromCharCode(charCode);
    }

    return btoa(result);
  }

  private static decrypt(encrypted: string): string {
    try {
      const text = atob(encrypted);
      const key = this.SECRET_KEY;
      let result = '';

      for (let i = 0; i < text.length; i++) {
        const charCode = text.charCodeAt(i) ^ key.charCodeAt(i % key.length);
        result += String.fromCharCode(charCode);
      }

      return result;
    } catch {
      return '';
    }
  }

  static setItem(key: string, value: string): void {
    try {
      const encrypted = this.encrypt(value);
      localStorage.setItem(key, encrypted);
    } catch (error) {
      logger.error('Failed to store encrypted data:', error as Error);
    }
  }

  static getItem(key: string): string | null {
    try {
      const encrypted = localStorage.getItem(key);
      if (!encrypted) return null;

      return this.decrypt(encrypted);
    } catch (error) {
      logger.error('Failed to retrieve encrypted data:', error as Error);
      return null;
    }
  }

  static removeItem(key: string): void {
    localStorage.removeItem(key);
  }
}

export default SecurityUtils;
