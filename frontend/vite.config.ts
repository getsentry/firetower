import path from 'path';

import {sentryVitePlugin} from '@sentry/vite-plugin';
import stylex from '@stylexjs/unplugin';
import {tanstackRouter} from '@tanstack/router-plugin/vite';
import react from '@vitejs/plugin-react-swc';
import {defineConfig} from 'vite';

const stylexPlugin = process.env.VITEST ? stylex.rollup : stylex.vite;

export default defineConfig({
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
      routeFileIgnorePattern: 'queries|components|types|utils|.*.test.tsx?',
    }),
    stylexPlugin({
      runtimeInjection: false,
      useCSSLayers: {
        before: ['reset'],
        prefix: 'stylex',
      },
    }),
    react(),
    sentryVitePlugin({
      org: 'sentry',
      project: 'firetower-frontend',
      disable: !process.env.SENTRY_AUTH_TOKEN,
      sourcemaps: {
        filesToDeleteAfterUpload: ['./dist/**/*.map'],
      },
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
