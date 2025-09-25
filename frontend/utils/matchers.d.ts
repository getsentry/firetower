import {TestingLibraryMatchers} from '@testing-library/jest-dom/matchers';
import {AsymmetricMatchers, Matchers} from 'bun:test';

declare module 'bun:test' {
  interface Matchers<T>
    extends TestingLibraryMatchers<typeof expect.stringContaining, T> {}
  interface AsymmetricMatchers extends TestingLibraryMatchers<any, any> {}
}
