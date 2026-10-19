import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function readHomamSlugs() {
  const source = fs.readFileSync(path.join(__dirname, 'src/data/homams.js'), 'utf8')
  return [...source.matchAll(/slug:\s*'([^']+)'/g)].map((m) => m[1])
}

/** Copy the SPA shell into each slug folder so IIS/Plesk can serve /homam/<slug>/ without URL Rewrite. */
function homamSlugPages() {
  return {
    name: 'homam-slug-pages',
    closeBundle() {
      const outDir = path.resolve(__dirname, '../homam')
      const indexPath = path.join(outDir, 'index.html')
      if (!fs.existsSync(indexPath)) return
      const indexHtml = fs.readFileSync(indexPath, 'utf8')
      for (const slug of readHomamSlugs()) {
        const dir = path.join(outDir, slug)
        fs.mkdirSync(dir, { recursive: true })
        fs.writeFileSync(path.join(dir, 'index.html'), indexHtml)
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), homamSlugPages()],
  // Absolute under /homam/ so nested slug URLs still load JS/CSS/images.
  base: '/homam/',
  build: {
    outDir: '../homam',
    emptyOutDir: true,
  },
})
