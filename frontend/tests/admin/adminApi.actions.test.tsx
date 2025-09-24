import { describe, it, expect, vi, beforeEach } from 'vitest'
import { SecureStorage } from '../../src/utils/security'
import { postCommunityDecision, postAnalysisFeedback } from '../../src/services/adminApi'

declare global { // eslint-disable-next-line no-var
  var fetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>
}

beforeEach(() => {
  // @ts-expect-error stub
  global.fetch = vi.fn(async (_input: RequestInfo, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(init!.body as string) : undefined
    const headers = (init?.headers as Headers) || new Headers()
    const resp = {
      ok: true,
      status: 200,
      json: async () => ({ code: 0, data: { event_id: 'eid' }, trace_id: 'tid' }),
      text: async () => JSON.stringify({ code: 0, data: { event_id: 'eid' }, trace_id: 'tid' }),
      headers: new Headers({ 'content-type': 'application/json' }),
    } as unknown as Response
    // attach for assertions
    // @ts-ignore
    resp._captured = { init, body, headers }
    return resp
  })
  // 存一个伪token
  SecureStorage.setItem('rss_token', 'test-token')
})

describe('adminApi actions', () => {
  it('posts community decision with auth header', async () => {
    const res = await postCommunityDecision({ community: 'r/test', action: 'approve' })
    expect(res.code).toBe(0)
    const lastCall = (global.fetch as any).mock.calls.at(-1)
    const init = lastCall[1] as RequestInit
    expect(init.method).toBe('POST')
    const headers = init.headers as Headers
    expect(headers.get('Authorization')).toMatch(/^Bearer /)
    expect(JSON.parse(init.body as string)).toMatchObject({ community: 'r/test', action: 'approve' })
  })

  it('posts analysis feedback', async () => {
    const res = await postAnalysisFeedback({ task_id: 't1', satisfied: true, reasons: [] })
    expect(res.code).toBe(0)
    const lastCall = (global.fetch as any).mock.calls.at(-1)
    const init = lastCall[1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toMatchObject({ task_id: 't1', satisfied: true })
  })
})

