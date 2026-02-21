import React from 'react';
import * as matchers from '@testing-library/jest-dom/matchers';
import {cleanup} from '@testing-library/react';
import {afterEach, expect} from 'bun:test';

// Polyfill React.act for React 19 compatibility (spencer: this is only an issue for my cursor-agent's shell it seems :shrug:)
if (!React.act) {
  // @ts-expect-error type not matching on override
  React.act = (callback: () => void | Promise<void>) => {
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
