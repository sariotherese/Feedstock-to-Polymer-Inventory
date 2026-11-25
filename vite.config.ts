import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  envDir: 'rayfin',
  define: {
    'import.meta.env.RAYFIN': JSON.stringify(
      Object.fromEntries(Object.entries(loadEnv(mode, 'rayfin', 'RAYFIN_PUBLIC_')))
    ),
  },
}));
