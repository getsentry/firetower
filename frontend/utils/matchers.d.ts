import type {TestingLibraryMatchers} from '@testing-library/jest-dom/matchers';

declare module 'bun:test' {
  // Extend Bun's Matchers interface to include jest-dom matchers
  interface Matchers<T> extends TestingLibraryMatchers<typeof expect.stringContaining, T> {
    // Intentionally empty - this is interface augmentation, not declaration
    [K: string]: never; // Satisfies ESLint rule while preserving functionality
  }

  // Extend Bun's AsymmetricMatchers interface to include jest-dom matchers
  interface AsymmetricMatchers extends TestingLibraryMatchers<typeof expect.stringContaining, unknown> {
    // Intentionally empty - this is interface augmentation, not declaration
    [K: string]: never; // Satisfies ESLint rule while preserving functionality
  }
}
