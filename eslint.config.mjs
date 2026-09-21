// Flat config (ESLint 9+), as .mjs so Node reads the ESM syntax
// without package.json having to declare the whole project a module.
// The frontend is one browser script, so the
// whole configuration is: which globals exist, and which mistakes matter.
export default [
  {
    files: ['web/assets/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',      // loaded with a plain <script src>, not a module
      globals: {
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        FormData: 'readonly',
        URLSearchParams: 'readonly',
        URL: 'readonly',
        Blob: 'readonly',
        setTimeout: 'readonly',
        Promise: 'readonly',
      },
    },
    rules: {
      // `catch (_)` is the idiom for "the error is not the point here";
      // caughtErrors defaults to 'all' in ESLint 9, so say so explicitly
      'no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
      'no-undef': 'error',
      eqeqeq: ['error', 'smart'],
      'no-var': 'error',
      'prefer-const': 'error',
    },
  },
];
