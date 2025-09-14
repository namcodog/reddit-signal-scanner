/**
 * 认证相关类型契约
 * 与backend/app/schemas/contracts/auth_contract.py对应
 */

export interface JWTPayload {
  sub: string; // user_id
  tenant: string; // tenant_id
  exp: number;
  iat: number;
  permissions: string[];
}

export interface UserContext {
  user_id: string;
  tenant_id: string;
  permissions: string[];
  session_id: string;
  expires_at: string; // ISO string
}

// 前端认证状态管理
export interface AuthState {
  isAuthenticated: boolean;
  user: UserContext | null;
  token: string | null;
  refreshToken: string | null;
  loading: boolean;
  error: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserContext;
}

// 认证相关组件Props
export interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions?: string[];
  fallback?: React.ReactNode;
}

export interface AuthContextProps {
  authState: AuthState;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshTokens: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
}