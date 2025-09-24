import { describe, it, beforeEach, expect, vi } from 'vitest';

vi.mock('@/services/api.client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock('@/utils/security', () => ({
  SecureStorage: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    getPersistence: vi.fn(),
  },
}));

import apiClient from '@/services/api.client';
import { SecureStorage } from '@/utils/security';
import { AUTH_ENDPOINTS, AUTH_STORAGE_KEYS } from '@/types/auth.types';

describe('AuthService 集成流', () => {
  const storage = new Map<string, string>();
  const hints = new Map<string, 'local' | 'session'>();

  const resetStorageMocks = () => {
    storage.clear();
    hints.clear();

    vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
      return storage.has(key) ? storage.get(key)! : null;
    });

    vi.mocked(SecureStorage.setItem).mockImplementation((
      key: string,
      value: string,
      options?: { persistent?: boolean }
    ) => {
      storage.set(key, value);
      const target = options?.persistent === false ? 'session' : 'local';
      hints.set(key, target);
    });

    vi.mocked(SecureStorage.removeItem).mockImplementation((key: string) => {
      storage.delete(key);
      hints.delete(key);
    });

    vi.mocked(SecureStorage.getPersistence).mockImplementation(
      (key: string) => hints.get(key) ?? null,
    );
  };

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    resetStorageMocks();
  });

  it('应该完成登录 → 刷新 → 登出的完整链路', async () => {
    const loginResponse = {
      access_token: 'login-access-token',
      refresh_token: 'login-refresh-token',
      token_type: 'bearer',
      expires_in: 3600,
      user_id: 'user-1',
      tenant_id: 'tenant-1',
      email: 'user@example.com',
    };

    const refreshedResponse = {
      access_token: 'refresh-access-token',
      refresh_token: 'refresh-refresh-token',
      token_type: 'bearer',
      expires_in: 7200,
      user_id: 'user-1',
      tenant_id: 'tenant-1',
      email: 'user@example.com',
    };

    const profileResponse = {
      id: 'user-1',
      tenant_id: 'tenant-1',
      email: 'user@example.com',
      email_verified: true,
      is_active: true,
      created_at: '2025-09-20T10:00:00Z',
      updated_at: '2025-09-20T10:10:00Z',
    };

    vi.mocked(apiClient.post)
      .mockResolvedValueOnce(loginResponse)
      .mockResolvedValueOnce(refreshedResponse)
      .mockResolvedValue({});

    vi.mocked(apiClient.get)
      .mockResolvedValueOnce(profileResponse)
      .mockResolvedValueOnce(profileResponse);

    const { AuthService } = await import('@/services/auth.service');

    const loginSession = await AuthService.login('user@example.com', 'StrongPass#123');

    const expectedUser = {
      id: 'user-1',
      tenantId: 'tenant-1',
      email: 'user@example.com',
      emailVerified: true,
      isActive: true,
      createdAt: '2025-09-20T10:00:00Z',
      updatedAt: '2025-09-20T10:10:00Z',
    };

    expect(loginSession).toEqual({
      user: expectedUser,
      accessToken: 'login-access-token',
      refreshToken: 'login-refresh-token',
      expiresIn: 3600,
    });

    expect(storage.get(AUTH_STORAGE_KEYS.TOKEN)).toBe('login-access-token');
    expect(storage.get(AUTH_STORAGE_KEYS.REFRESH_TOKEN)).toBe('login-refresh-token');
    expect(storage.get(AUTH_STORAGE_KEYS.USER)).toBe(JSON.stringify(expectedUser));
    expect(hints.get(AUTH_STORAGE_KEYS.TOKEN)).toBe('local');

    const refreshedSession = await AuthService.refreshToken();

    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      AUTH_ENDPOINTS.REFRESH,
      null,
      expect.objectContaining({
        headers: { Authorization: 'Bearer login-refresh-token' },
      }),
    );

    expect(refreshedSession).toEqual({
      user: expectedUser,
      accessToken: 'refresh-access-token',
      refreshToken: 'refresh-refresh-token',
      expiresIn: 7200,
    });

    expect(storage.get(AUTH_STORAGE_KEYS.TOKEN)).toBe('refresh-access-token');
    expect(storage.get(AUTH_STORAGE_KEYS.REFRESH_TOKEN)).toBe('refresh-refresh-token');
    expect(storage.get('last_token_refresh')).not.toBeUndefined();

    await AuthService.logout();

    expect(apiClient.post).toHaveBeenNthCalledWith(3, AUTH_ENDPOINTS.LOGOUT);
    expect(storage.get(AUTH_STORAGE_KEYS.TOKEN)).toBeUndefined();
    expect(storage.get(AUTH_STORAGE_KEYS.USER)).toBeUndefined();
    expect(storage.get(AUTH_STORAGE_KEYS.REFRESH_TOKEN)).toBeUndefined();
  });
});
