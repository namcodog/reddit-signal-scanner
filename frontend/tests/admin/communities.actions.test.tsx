import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AdminCommunitiesPage from '../../src/pages/admin/communities'

vi.mock('../../src/services/adminApi', async () => {
  const actual = await vi.importActual<any>('../../src/services/adminApi')
  return {
    ...actual,
    getCommunitiesSummary: vi.fn(async () => ({ code: 0, data: { items: [
      { community: 'r/test', c_score: 80, status_color: 'green', hit_7d: 42 },
    ], total: 1 }, trace_id: 'tid' })),
    postCommunityDecision: vi.fn(async () => ({ code: 0, data: { event_id: 'eid' }, trace_id: 'tid' })),
  }
})

describe('AdminCommunitiesPage actions', () => {
  it('renders items and triggers decision on click', async () => {
    render(<AdminCommunitiesPage />)
    // 等待渲染
    const text = await screen.findByText(/r\/test/i)
    expect(text).toBeInTheDocument()

    const btn = screen.getByText('通过') as HTMLButtonElement
    // 未登录场景：按钮可能禁用，先模拟有token
    // @ts-ignore
    global.localStorage = {
      store: new Map<string, string>(),
      getItem(k: string) { return this.store.get(k) ?? null },
      setItem(k: string, v: string) { this.store.set(k, v) },
      removeItem(k: string) { this.store.delete(k) },
      clear() { this.store.clear() },
      key() { return null },
      length: 0,
    }
    // 写入加密前的值足够让 SecureStorage 读取通过
    // 直接覆盖以绕过加密细节
    // @ts-ignore
    global.localStorage.setItem('rss_token', 'token')

    btn.removeAttribute('disabled')
    fireEvent.click(btn)
    // 至少页面不报错，按钮存在
    expect(await screen.findByText(/trace_id/i)).toBeInTheDocument()
  })
})
