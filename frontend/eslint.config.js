import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import eslintPluginTailwindCSS from 'eslint-plugin-tailwindcss';
import {globalIgnores} from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
      eslintPluginTailwindCSS.configs['flat/recommended'],
    ],
    settings: {
      tailwindcss: {
        // For Tailwind v4 - disable config path since it uses CSS-based config
        config: false,
        // Specify CSS files where Tailwind is defined
        cssFiles: ["src/styles/index.css", "src/styles/design-tokens.css"],
      },
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
]);
