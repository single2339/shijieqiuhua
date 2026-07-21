import { constants } from 'zlib'
import { promisify } from 'util'
import { brotliCompress, gzip } from 'zlib'
import { fileURLToPath } from 'url'
import { readdir, readFile, stat, writeFile } from 'fs/promises'
import { extname, resolve } from 'path'

const gzipAsync = promisify(gzip)
const brotliAsync = promisify(brotliCompress)
const COMPRESSIBLE_EXTENSIONS = new Set(['.css', '.html', '.js', '.json', '.svg'])
const MINIMUM_BYTES = 1024

async function assetPaths(root) {
  const paths = []
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name)
    if (entry.isDirectory()) paths.push(...await assetPaths(path))
    else if (entry.isFile() && COMPRESSIBLE_EXTENSIONS.has(extname(entry.name))) paths.push(path)
  }
  return paths
}

export async function compressBuildAssets(root) {
  let compressed = 0
  for (const path of await assetPaths(resolve(root))) {
    if ((await stat(path)).size < MINIMUM_BYTES) continue
    const source = await readFile(path)
    const [gzipOutput, brotliOutput] = await Promise.all([
      gzipAsync(source, { level: 9 }),
      brotliAsync(source, {
        params: {
          [constants.BROTLI_PARAM_QUALITY]: 9,
        },
      }),
    ])
    if (gzipOutput.length < source.length) await writeFile(`${path}.gz`, gzipOutput)
    if (brotliOutput.length < source.length) await writeFile(`${path}.br`, brotliOutput)
    compressed += 1
  }
  return compressed
}

const currentFile = fileURLToPath(import.meta.url)
if (process.argv[1] && resolve(process.argv[1]) === currentFile) {
  const root = resolve(process.argv[2] ?? fileURLToPath(new URL('../dist', import.meta.url)))
  const count = await compressBuildAssets(root)
  console.log(`Compressed ${count} production assets with gzip and brotli.`)
}
