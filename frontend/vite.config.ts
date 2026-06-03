import path from 'path';

import {sentryVitePlugin} from '@sentry/vite-plugin';
import tailwindcss from '@tailwindcss/vite';
import {tanstackRouter} from '@tanstack/router-plugin/vite';
import react from '@vitejs/plugin-react-swc';
import {defineConfig} from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
      routeFileIgnorePattern: 'queries|components|types|utils|.*.test.tsx?',
    }),
    tailwindcss(),
    react(),
    sentryVitePlugin({
      org: 'sentry',
      project: 'firetower-frontend',
    }),
  ],

  resolve: {
    alias: {
      components: path.resolve(__dirname, './src/components'),
      utils: path.resolve(__dirname, './src/utils'),
      api: path.resolve(__dirname, './src/api.ts'),
    },
  },

  test: {
    setupFiles: ['./utils/happydom.ts', './utils/testing-library.ts'],
  },

  build: {
    sourcemap: true,
  },
});
