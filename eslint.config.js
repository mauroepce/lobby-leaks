import js from '@eslint/js';
import globals from 'globals';

/** @type {import('eslint').Linter.FlatConfig[]} */
export default [
  js.configs.recommended,

  // Reglas generales para todo .js
  {
    files: ['**/*.js'],
    ignores: ['**/node_modules/**'],
    languageOptions: {
      globals: {
        ...globals.node
      }
    },
    rules: {
      semi: ['error', 'always'],
      quotes: ['error', 'single']
    }
  },

  // Excepción: tests con Jest
  {
    files: ['tests/**/*.js'],
    languageOptions: {
      globals: {
        ...globals.jest
      }
    }
  }
];
