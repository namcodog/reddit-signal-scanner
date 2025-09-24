/**
 * Phase4 用户管理系统类型定义
 * 支持会员等级、使用统计、分析历史等功能
 */

// 会员等级枚举（与后端MembershipLevel对齐）
export enum MembershipLevel {
  FREE = 'free',
  PRO = 'pro',
  ENTERPRISE = 'enterprise',
}

// 扩展的用户信息接口（前端使用camelCase）
export interface UserProfile {
  id: string;
  tenantId: string;
  email: string;
  emailVerified: boolean;
  isActive: boolean;
  membershipLevel: MembershipLevel;
  createdAt: string;
  updatedAt: string;
}

// 用户分析历史项（前端友好字段）
export interface UserHistoryItem {
  taskId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'dead_letter';
  statusLabel: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string | null;
  description?: string | null;
}

// 历史列表响应（用于前端分页逻辑）
export interface UserHistoryResponse {
  items: UserHistoryItem[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
}

// 用户使用统计
export interface UserUsageStats {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  activeTasks: number;
  pendingTasks: number;
  currentMonthTotal: number;
  currentMonthQuota: number | null;
  remainingQuota: number | null;
  lastActivityAt?: string | null;
}

// 后端返回的会员权益信息
export interface MembershipFeatureFlags {
  canExportReport: boolean;
  realtimeUpdates: boolean;
  prioritySupport: boolean;
  maxTasksPerMonth: number | null;
  highlight?: string | null;
}

export interface MembershipInfo {
  level: MembershipLevel;
  label: string;
  usedThisMonth: number;
  remainingQuota: number | null;
  quota: number | null;
  features: MembershipFeatureFlags;
  upgradeOptions: MembershipLevel[];
}

// 会员升级请求（前端侧）
export interface MembershipUpgradeRequest {
  targetLevel: MembershipLevel;
}

// 用户资料更新请求
export interface UserProfileUpdateRequest {
  email?: string;
}

// 修改密码请求
export interface PasswordChangeRequest {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

// 安全设置接口
export interface SecuritySettings {
  passwordLastChanged: string;
  twoFactorEnabled: boolean;
  loginSessions: Array<{
    id: string;
    deviceInfo: string;
    ipAddress: string;
    lastActive: string;
    isCurrent: boolean;
  }>;
}

// API端点常量
export const USER_ENDPOINTS = {
  PROFILE: '/api/v1/users/me',
  HISTORY: '/api/v1/users/me/history',
  USAGE: '/api/v1/users/me/usage',
  MEMBERSHIP: '/api/v1/users/me/membership',
  UPGRADE: '/api/v1/users/me/membership',
  CHANGE_PASSWORD: '/api/v1/users/change-password',
} as const;

// 会员功能权限配置（用于前端展示/默认值）
export const MEMBERSHIP_FEATURES = {
  [MembershipLevel.FREE]: {
    monthlyQuota: 10,
    features: ['基础分析', '标准报告'],
    canExportPdf: false,
    hasRealtimeUpdates: false,
    priority: 'low',
  },
  [MembershipLevel.PRO]: {
    monthlyQuota: 100,
    features: ['高级分析', 'PDF导出', '实时更新', '邮件通知'],
    canExportPdf: true,
    hasRealtimeUpdates: true,
    priority: 'high',
  },
  [MembershipLevel.ENTERPRISE]: {
    monthlyQuota: null, // 无限制
    features: ['企业级分析', 'API访问', '专属支持', '自定义集成'],
    canExportPdf: true,
    hasRealtimeUpdates: true,
    priority: 'highest',
  },
} as const;

// 会员等级显示配置
export const MEMBERSHIP_DISPLAY = {
  [MembershipLevel.FREE]: {
    name: '免费版',
    color: '#64748b',
    badge: '免费',
    description: '适合个人用户基础分析需求',
  },
  [MembershipLevel.PRO]: {
    name: '专业版',
    color: '#3b82f6',
    badge: 'PRO',
    description: '适合专业用户和小团队',
  },
  [MembershipLevel.ENTERPRISE]: {
    name: '企业版',
    color: '#7c3aed',
    badge: '企业',
    description: '适合大型团队和企业用户',
  },
} as const;
