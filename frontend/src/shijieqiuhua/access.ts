import { ACTIVATION_CODES, INVITATIONS } from './mockData'
import type { AccessMode, ActivationCode, InvitationCode, UserProfile } from './types'

export function getAccessMode(user: UserProfile | null): AccessMode {
  return user?.status ?? 'public'
}

export function canUseFullAnalysis(user: UserProfile | null): boolean {
  return getAccessMode(user) === 'paid'
}

export function validateInviteCode(code: string, invitations: InvitationCode[] = INVITATIONS) {
  const clean = code.trim().toUpperCase()
  const invitation = invitations.find(item => item.code === clean)
  if (!invitation) return { ok: false as const, reason: '邀请码不存在' }
  if (invitation.usedBy) return { ok: false as const, reason: '邀请码已被使用' }
  if (new Date(invitation.expiresAt).getTime() < Date.now()) return { ok: false as const, reason: '邀请码已过期' }
  return { ok: true as const, code: invitation.code }
}

export function createRegisteredUser(name: string, inviteCode: string): UserProfile {
  return {
    id: `u-${Date.now().toString(36)}`,
    name: name.trim() || '新球花用户',
    status: 'registered_unpaid',
    inviteCodeUsed: inviteCode.trim().toUpperCase(),
  }
}

export function createInvitation(user: UserProfile | null) {
  if (!user || user.status !== 'paid') {
    return { ok: false as const, reason: '开通完整功能后才能邀请新用户' }
  }
  return {
    ok: true as const,
    code: `SQH-${user.id.slice(-4).toUpperCase()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
  }
}

export function redeemActivationCode(
  user: UserProfile | null,
  code: string,
  codes: ActivationCode[] = ACTIVATION_CODES,
) {
  if (!user) return { ok: false as const, reason: '请先使用邀请码注册', codes }
  const clean = code.trim().toUpperCase()
  const target = codes.find(item => item.code === clean)
  if (!target) return { ok: false as const, reason: '付费码不存在', codes }
  if (target.used) return { ok: false as const, reason: '付费码已被使用', codes }
  const nextCodes = codes.map(item => item.code === clean ? { ...item, used: true, redeemedBy: user.id } : item)
  return { ok: true as const, user: { ...user, status: 'paid' as const }, codes: nextCodes }
}
