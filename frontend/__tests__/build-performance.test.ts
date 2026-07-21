import { execFileSync } from 'child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join, resolve } from 'path'
import { describe, expect, test } from 'vitest'

const frontendRoot = resolve(__dirname, '..')
const compressionScript = resolve(frontendRoot, 'scripts/compress-dist.mjs')
const packageJson = JSON.parse(readFileSync(resolve(frontendRoot, 'package.json'), 'utf-8'))

describe('production asset performance', () => {
  test('production build runs static asset compression', () => {
    expect(packageJson.scripts.build).toContain('node scripts/compress-dist.mjs')
  })

  test('large JavaScript assets receive smaller gzip and brotli siblings', () => {
    expect(existsSync(compressionScript)).toBe(true)
    if (!existsSync(compressionScript)) return

    const output = mkdtempSync(join(tmpdir(), 'osint-compress-'))
    try {
      const asset = join(output, 'map.js')
      writeFileSync(asset, 'const repeated = "maplibre";\n'.repeat(20_000))

      execFileSync(process.execPath, [compressionScript, output])

      expect(existsSync(`${asset}.gz`)).toBe(true)
      expect(existsSync(`${asset}.br`)).toBe(true)
      expect(statSync(`${asset}.gz`).size).toBeLessThan(statSync(asset).size)
      expect(statSync(`${asset}.br`).size).toBeLessThan(statSync(`${asset}.gz`).size)
    } finally {
      rmSync(output, { recursive: true, force: true })
    }
  })
})
