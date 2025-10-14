import React from 'react';
import * as matchers from '@testing-library/jest-dom/matchers';
import {cleanup} from '@testing-library/react';
import {afterEach, expect} from 'bun:test';

// Polyfill React.act for React 19 compatibility (seems to only be an issue with my cursor-agent's shell :shrug:)
// @ts-expect-error - Adding act polyfill for testing
if (!React.act) {
  // @ts-expect-error - Adding act polyfill for testing
  React.act = callback => {
    const result = callback();
    if (result && typeof result.then === 'function') {
      return result;
    }
    return Promise.resolve();
  };
}

expect.extend(matchers);

// Optional: cleans up `render` after each test
afterEach(() => {
  cleanup();
});
