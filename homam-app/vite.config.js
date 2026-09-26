import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Relative so file:// and any static host work; FastAPI still serves /homam/*
  base: './',
  build: {
    outDir: '../homam',
    emptyOutDir: true,
  },
})
