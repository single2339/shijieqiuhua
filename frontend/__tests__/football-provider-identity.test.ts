import { describe, expect, it } from 'vitest'
import { fixtureToMatch } from '../src/shijieqiuhua/mockData'

describe('football provider identity', () => {
  it('preserves provider identity when mapping fixture to match', () => {
    const match = fixtureToMatch({
      id: '537424',
      provider: 'football-data',
      provider_match_id: '537424',
      home_provider_id: '808',
      away_provider_id: '816',
      league: '世界杯',
      kickoff_at: '07-01 01:00',
      kickoff_iso: '2026-06-30T17:00:00+00:00',
      home_team: '科特迪瓦',
      away_team: '挪威',
      status: 'scheduled',
      home_score: null,
      away_score: null,
    })

    expect(match.provider).toBe('football-data')
    expect(match.provider_match_id).toBe('537424')
    expect(match.home_provider_id).toBe('808')
    expect(match.away_provider_id).toBe('816')
  })
})
