/**
 * HTTP客户端工具 - 遵循Linus简洁原则
 * 单一职责：只处理HTTP请求，不管验证和加密
 */

/**
 * 简化的HTTP客户端
 * Linus: "做一件事，做好它"
 */
export class HttpClient {
  private static csrfToken: string | null = null;

  /**
   * 获取或生成CSRF Token
   */
  private static getCSRFToken(): string {
    if (!this.csrfToken) {
      const array = new Uint8Array(16);
      crypto.getRandomValues(array);
      this.csrfToken = Array.from(array, byte =>
        byte.toString(16).padStart(2, '0')
      ).join('');
      sessionStorage.setItem('csrf_token', this.csrfToken);
    }
    return this.csrfToken;
  }

  /**
   * 安全的POST请求
   */
  static async post<T>(url: string, data: object): Promise<T> {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-Token': this.getCSRFToken(),
      },
      credentials: 'same-origin',
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '网络错误');
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    return response.json();
  }

  /**
   * GET请求
   */
  static async get<T>(url: string): Promise<T> {
    const response = await fetch(url, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }
}

export default HttpClient;
