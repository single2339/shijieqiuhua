import { describe, expect, test, vi } from 'vitest'
import { downloadTextFile } from '../src/utils/download'

describe('downloadTextFile', () => {
  test('uses an attached anchor and delays object URL cleanup until after the click', async () => {
    const click = vi.fn()
    const remove = vi.fn()
    const appendChild = vi.fn()
    const link = { href: '', download: '', style: { display: '' }, click, remove }
    const createObjectURL = vi.fn(() => 'blob:super-analysis')
    const revokeObjectURL = vi.fn()
    let cleanup: (() => void) | undefined
    let cleanupDelay = 0
    const setTimeout = vi.fn((callback: () => void, delay: number) => {
      cleanup = callback
      cleanupDelay = delay
      return 1
    })
    vi.stubGlobal('document', {
      createElement: vi.fn(() => link),
      body: { appendChild },
    })
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    vi.stubGlobal('window', { setTimeout })

    try {
      downloadTextFile('超级分析报告.html', '<!doctype html><p>报告内容</p>', 'text/html;charset=utf-8')

      expect(appendChild).toHaveBeenCalledWith(link)
      expect(link.href).toBe('blob:super-analysis')
      expect(link.download).toBe('超级分析报告.html')
      expect(link.style.display).toBe('none')
      expect(click).toHaveBeenCalledOnce()
      expect(remove).toHaveBeenCalledOnce()
      expect(revokeObjectURL).not.toHaveBeenCalled()
      expect(cleanupDelay).toBeGreaterThan(0)

      const blob = createObjectURL.mock.calls[0][0] as Blob
      expect(blob.type).toBe('text/html;charset=utf-8')
      expect(await blob.text()).toBe('<!doctype html><p>报告内容</p>')

      expect(cleanup).toBeTypeOf('function')
      cleanup?.()
      expect(revokeObjectURL).toHaveBeenCalledWith('blob:super-analysis')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
