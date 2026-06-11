# Shijieqiuhua Web MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Web MVP for “世界球花” with the approved brand direction, match question card, invite-only registration gate, and paid-access gate.

**Architecture:** Keep the first implementation frontend-only with deterministic local data and pure access-control helpers. This creates a usable product shell now while preserving clear contracts for later backend, payment, and mini-program integration.

**Tech Stack:** React 19, Vite, TypeScript, Vitest, Framer Motion, `@phosphor-icons/react`, CSS modules via a dedicated stylesheet.

---

## File Structure

- Create `frontend/src/shijieqiuhua/types.ts`: Domain types for matches, questions, evidence, access states, invitations, and activation codes.
- Create `frontend/src/shijieqiuhua/mockData.ts`: Stable demo matches, public summaries, evidence, invite code, and activation code seeds.
- Create `frontend/src/shijieqiuhua/access.ts`: Pure functions for access mode, feature gates, invitation creation, invite validation, and activation-code redemption.
- Create `frontend/__tests__/shijieqiuhua-access.test.ts`: Unit tests for the access model.
- Replace `frontend/src/App.tsx`: Render the World Ball Flower Web MVP instead of the OSINT dashboard in this worktree.
- Create `frontend/src/shijieqiuhua.css`: Brand and responsive layout styles for the Web MVP.

## Task 1: Domain Model And Access Rules

**Files:**
- Create: `frontend/src/shijieqiuhua/types.ts`
- Create: `frontend/src/shijieqiuhua/mockData.ts`
- Create: `frontend/src/shijieqiuhua/access.ts`
- Test: `frontend/__tests__/shijieqiuhua-access.test.ts`

- [ ] **Step 1: Write failing access tests**

Create `frontend/__tests__/shijieqiuhua-access.test.ts`:

```ts
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd frontend && npm test -- shijieqiuhua-access.test.ts`

Expected: FAIL because `../src/shijieqiuhua/access` does not exist.

- [ ] **Step 3: Implement domain types**

Create `frontend/src/shijieqiuhua/types.ts`:

```ts
export type AccessMode = 'public' | 'registered_unpaid' | 'paid'
export type QuestionDimension = 'half' | 'cards' | 'corners' | 'goals' | 'player' | 'risk'
export type EvidenceStrength = 'strong' | 'weak' | 'insufficient'

export interface UserProfile {
  id: string
  name: string
  status: Exclude<AccessMode, 'public'>
  inviteCodeUsed: string
}

export interface InvitationCode {
  code: string
  inviterId: string
  usedBy?: string
  expiresAt: string
}

export interface ActivationCode {
  code: string
  used: boolean
  redeemedBy?: string
}

export interface EvidenceItem {
  id: string
  strength: EvidenceStrength
  title: string
  source: string
}

export interface MatchQuestion {
  id: QuestionDimension
  label: string
  prompt: string
}

export interface MatchPrediction {
  home: number
  draw: number
  away: number
  confidence: number
  rating: 'L1' | 'L2' | 'L3' | 'L4'
  summary: string
}

export interface FootballMatch {
  id: string
  league: string
  kickoffAt: string
  homeTeam: string
  awayTeam: string
  publicLean: string
  prediction: MatchPrediction
  questions: MatchQuestion[]
  evidence: EvidenceItem[]
  riskFlags: string[]
}
```

- [ ] **Step 4: Implement mock data**

Create `frontend/src/shijieqiuhua/mockData.ts`:

```ts
import type { ActivationCode, FootballMatch, InvitationCode } from './types'

export const QUESTION_PRESETS = [
  { id: 'half', label: '半场', prompt: '上半场哪一方更容易占据主动？' },
  { id: 'cards', label: '红黄牌', prompt: '本场红黄牌风险是否偏高？' },
  { id: 'corners', label: '角球', prompt: '上半场角球会不会偏多？' },
  { id: 'goals', label: '进球数', prompt: '全场进球数压力更偏大还是偏小？' },
  { id: 'player', label: '球员', prompt: '核心球员状态会怎样影响比赛？' },
  { id: 'risk', label: '风险', prompt: '这场比赛最大的临场风险是什么？' },
] as const

export const MATCHES: FootballMatch[] = [
  {
    id: 'wc-arg-ksa',
    league: '世界杯 A组',
    kickoffAt: '今晚 20:00',
    homeTeam: '阿根廷',
    awayTeam: '沙特阿拉伯',
    publicLean: '主队方向略优',
    prediction: {
      home: 68,
      draw: 21,
      away: 11,
      confidence: 74,
      rating: 'L2',
      summary: '主队前场创造力与核心球员状态更稳定，但客队中场拦截效率会压低结论强度。',
    },
    questions: [...QUESTION_PRESETS],
    evidence: [
      { id: 'e1', strength: 'strong', title: '核心攻击手近三场参与进球稳定', source: 'team-form-feed' },
      { id: 'e2', strength: 'weak', title: '客队中场拦截效率稳定，具备限制节奏能力', source: 'match-preview' },
      { id: 'e3', strength: 'insufficient', title: '裁判出牌尺度样本不足，红牌结论需谨慎', source: 'referee-watch' },
    ],
    riskFlags: ['赛前名单仍有不确定性', '不使用市场价格模型'],
  },
  {
    id: 'wc-pol-mex',
    league: '世界杯 A组',
    kickoffAt: '今晚 23:00',
    homeTeam: '波兰',
    awayTeam: '墨西哥',
    publicLean: '平局压力偏高',
    prediction: {
      home: 34,
      draw: 36,
      away: 30,
      confidence: 61,
      rating: 'L3',
      summary: '双方防守完整度接近，比赛可能更依赖定位球和半场节奏变化。',
    },
    questions: [...QUESTION_PRESETS],
    evidence: [
      { id: 'e4', strength: 'strong', title: '双方近期失球控制都较稳定', source: 'form-check' },
      { id: 'e5', strength: 'weak', title: '客队边路推进可能制造角球数量', source: 'tactical-brief' },
      { id: 'e6', strength: 'insufficient', title: '临场天气对节奏影响暂不明确', source: 'venue-weather' },
    ],
    riskFlags: ['平局压力较高', '角球结论需要临场阵容确认'],
  },
]

export const INVITATIONS: InvitationCode[] = [
  { code: 'QH-2026-SEED', inviterId: 'seed-user', expiresAt: '2026-12-31T23:59:59.000Z' },
  { code: 'USED-2026', inviterId: 'seed-user', usedBy: 'u-old', expiresAt: '2026-12-31T23:59:59.000Z' },
]

export const ACTIVATION_CODES: ActivationCode[] = [
  { code: 'PAY-2026-FULL', used: false },
]
```

- [ ] **Step 5: Implement access helpers**

Create `frontend/src/shijieqiuhua/access.ts`:

```ts
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
  if (!canUseFullAnalysis(user)) {
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
```

- [ ] **Step 6: Run tests to verify pass**

Run: `cd frontend && npm test -- shijieqiuhua-access.test.ts`

Expected: PASS for all access tests.

## Task 2: Web MVP UI

**Files:**
- Replace: `frontend/src/App.tsx`
- Create: `frontend/src/shijieqiuhua.css`
- Modify: `frontend/src/main.tsx` only if the old auth wrapper causes runtime issues.

- [ ] **Step 1: Replace `App.tsx` with the Shijieqiuhua app shell**

Implement a single React app that imports `MATCHES`, `ACTIVATION_CODES`, and access helpers. It must render:

- Brand header: “世界球花”.
- Left match queue on desktop.
- Central `MatchQuestionCard`.
- Right account panel with invite registration, payment-code redemption, and invitation generation.
- Mobile bottom navigation visual affordance.
- Public, registered unpaid, and paid states.

The component must not use emoji in UI text or icons. Use `@phosphor-icons/react` icons.

- [ ] **Step 2: Add `shijieqiuhua.css`**

Create the “绿茵纸感” visual system:

- Deep green brand surfaces.
- Grass-gold confidence ring and accents.
- Warm paper background.
- Stable responsive layout for desktop and mobile.
- No hero landing page; first screen is the usable app.

- [ ] **Step 3: Run TypeScript build**

Run: `cd frontend && npm run build`

Expected: PASS.

## Task 3: Verification And Commit

**Files:**
- Verify all files changed by Tasks 1-2.

- [ ] **Step 1: Run focused tests**

Run: `cd frontend && npm test -- shijieqiuhua-access.test.ts`

Expected: PASS.

- [ ] **Step 2: Run full frontend tests**

Run: `cd frontend && npm test`

Expected: PASS. If old OSINT-specific tests fail because the project purpose changed, document the failing test and update only tests that assert obsolete app-shell behavior.

- [ ] **Step 3: Run build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/shijieqiuhua.css frontend/src/shijieqiuhua frontend/__tests__/shijieqiuhua-access.test.ts docs/superpowers/plans/2026-06-11-shijieqiuhua-web-mvp.md
git commit -m "feat: build Shijieqiuhua web MVP"
```

## Self-Review

- Spec coverage: This MVP covers brand direction, Web-enhanced layout, match question card, public/registered/paid access states, invite registration, activation-code unlock, evidence visibility, report preview, and invitation generation. It intentionally does not implement real backend auth, real payment callbacks, or mini-program code.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps.
- Type consistency: Access states use `public`, `registered_unpaid`, and `paid` consistently across tests, helpers, and UI.
