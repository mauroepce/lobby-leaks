import js from '@eslint/js';
import globals from 'globals';

/** @type {import('eslint').Linter.FlatConfig[]} */
export default [
  js.configs.recommended,
   {
    ignores: [
      '**/node_modules/**',
      'clients/ts/**'
    ]
  },
  // Reglas generales para todo .js
  {
    files: ['**/*.js'],
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
