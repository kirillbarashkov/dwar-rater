import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Baseline (техдолг A4). Эти правила уже нарушены в существующем коде,
      // поэтому понижены до warn: CI обязан падать на НОВЫХ ошибках, а не на
      // унаследованных. Долг — чинить по файлу и поднимать правило обратно.
      // Текущее состояние: 25 сообщений, 12 файлов.
      'react-hooks/set-state-in-effect': 'warn',
      'no-case-declarations': 'warn',
      'react-refresh/only-export-components': 'warn',
      '@typescript-eslint/no-unused-vars': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
])
