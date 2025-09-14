/*
 * 前端通用日志工具：在开发环境或手动开启调试时输出 debug/info，
 * 生产环境默认仅输出 warn/error，避免噪音泄漏。
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

const DEBUG_STORAGE_KEY = "app.debug";

function isDevEnvironment(): boolean {
  try {
    // Vite 提供的运行时标志
    const meta: unknown = typeof import.meta !== "undefined" ? import.meta : {};
    if (
      typeof meta === "object" &&
      meta !== null &&
      "env" in meta &&
      typeof (meta as { env?: { DEV?: unknown } }).env === "object" &&
      (meta as { env?: { DEV?: unknown } }).env !== null &&
      typeof (meta as { env: { DEV?: unknown } }).env.DEV === "boolean"
    ) {
      return Boolean((meta as { env: { DEV: boolean } }).env.DEV);
    }
  } catch (e) {
    // ignore environment detection errors and fallback below
  }
  return typeof process !== "undefined" && process.env && process.env.NODE_ENV === "development";
}

function isDebugEnabled(): boolean {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem(DEBUG_STORAGE_KEY) === "true";
    }
  } catch (e) {
    // localStorage might be blocked; default to false
  }
  return false;
}

function shouldLog(level: LogLevel): boolean {
  if (level === "warn" || level === "error") return true;
  return isDevEnvironment() || isDebugEnabled();
}

const logger = {
  debug: (...args: unknown[]): void => {
    if (shouldLog("debug")) {
      // eslint-disable-next-line no-console
      console.debug(...args);
      // 同步到 console.log 以兼容既有测试断言
      // eslint-disable-next-line no-console
      console.log(...args);
    }
  },
  info: (...args: unknown[]): void => {
    if (shouldLog("info")) {
      // eslint-disable-next-line no-console
      console.info(...args);
      // 同步到 console.log 以兼容既有测试断言
      // eslint-disable-next-line no-console
      console.log(...args);
    }
  },
  warn: (...args: unknown[]): void => {
    // eslint-disable-next-line no-console
    console.warn(...args);
  },
  error: (...args: unknown[]): void => {
    // eslint-disable-next-line no-console
    console.error(...args);
  },
  enableDebug: (): void => {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.setItem(DEBUG_STORAGE_KEY, "true");
      }
    } catch (e) {
      // ignore
    }
  },
  disableDebug: (): void => {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.removeItem(DEBUG_STORAGE_KEY);
      }
    } catch (e) {
      // ignore
    }
  },
  isDebugOn: (): boolean => isDebugEnabled(),
};

export default logger;
