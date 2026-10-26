import js from '@eslint/js';
import {rules as stylexRules} from '@stylexjs/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import {globalIgnores} from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';

import stylexOnly from './eslint-rules/stylex-only.mjs';

export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: {
      '@stylexjs': {rules: stylexRules},
      local: {rules: {'stylex-only': stylexOnly}},
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      '@stylexjs/valid-styles': 'error',
      '@stylexjs/enforce-extension': 'error',
      'local/stylex-only': 'error',
      'no-restricted-imports': [
        'error',
        {
          paths: [
            'classnames',
            'class-variance-authority',
            'tailwind-merge',
            'tailwindcss',
            '@tailwindcss/vite',
            'utils/cn',
          ],
          patterns: ['**/utils/cn', '**/cn', '@tailwindcss/*', '**/*.css', '**/*.scss'],
        },
      ],
    },
  },
]);
