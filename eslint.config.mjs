// Flat config (ESLint 9+), as .mjs so Node reads the ESM syntax
// without package.json having to declare the whole project a module.
// The frontend is one browser script, so the
// whole configuration is: which globals exist, and which mistakes matter.
export default [
  // third-party, minified, not ours to lint or reformat
  { ignores: ['web/assets/vendor/**'] },
  {
    files: ['web/assets/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',      // <script type="module">, with imports
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
        clearTimeout: 'readonly',
        Promise: 'readonly',
        AbortController: 'readonly',
        TextDecoder: 'readonly',
        indexedDB: 'readonly',
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
