import { describe, expect, test } from 'vitest'
import {
  canUseFullAnalysis,
  createInvitation,
  getAccessMode,
  redeemActivationCode,
  validateInviteCode,
} from '../src/shijieqiuhua/access'
import type { ActivationCode, UserProfile } from '../src/shijieqiuhua/types'

describe('shijieqiuhua access rules', () => {
  test('anonymous users only get public access', () => {
    expect(getAccessMode(null)).toBe('public')
    expect(canUseFullAnalysis(null)).toBe(false)
  })

  test('registered unpaid users cannot use full analysis', () => {
    const user: UserProfile = { id: 'u1', name: '林观球', status: 'registered_unpaid', inviteCodeUsed: 'QH-2026' }
    expect(getAccessMode(user)).toBe('registered_unpaid')
    expect(canUseFullAnalysis(user)).toBe(false)
  })

  test('paid users can use full analysis', () => {
    const user: UserProfile = { id: 'u2', name: '周临场', status: 'paid', inviteCodeUsed: 'QH-2026' }
    expect(getAccessMode(user)).toBe('paid')
    expect(canUseFullAnalysis(user)).toBe(true)
  })

  test('invite code validation requires unused and unexpired codes', () => {
    expect(validateInviteCode('QH-2026-SEED')).toEqual({ ok: true, code: 'QH-2026-SEED' })
    expect(validateInviteCode('USED-2026')).toEqual({ ok: false, reason: '邀请码已被使用' })
    expect(validateInviteCode('MISSING')).toEqual({ ok: false, reason: '邀请码不存在' })
  })

  test('only paid users can generate invitation codes', () => {
    const unpaid: UserProfile = { id: 'u1', name: '林观球', status: 'registered_unpaid', inviteCodeUsed: 'QH-2026' }
    expect(createInvitation(unpaid)).toEqual({ ok: false, reason: '开通完整功能后才能邀请新用户' })
    const paid: UserProfile = { id: 'u2', name: '周临场', status: 'paid', inviteCodeUsed: 'QH-2026' }
    const result = createInvitation(paid)
    expect(result.ok).toBe(true)
    expect(result.code).toMatch(/^SQH-/)
  })

  test('activation code redemption upgrades registered users once', () => {
    const codes: ActivationCode[] = [{ code: 'PAY-2026-FULL', used: false }]
    const user: UserProfile = { id: 'u1', name: '林观球', status: 'registered_unpaid', inviteCodeUsed: 'QH-2026' }
    const result = redeemActivationCode(user, 'PAY-2026-FULL', codes)
    expect(result.ok).toBe(true)
    expect(result.user?.status).toBe('paid')
    expect(result.codes[0].used).toBe(true)
    expect(redeemActivationCode(user, 'PAY-2026-FULL', result.codes)).toEqual({
      ok: false,
      reason: '付费码已被使用',
      codes: result.codes,
    })
  })
})
