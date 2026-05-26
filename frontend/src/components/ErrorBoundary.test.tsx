import {render, screen} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

import {ErrorBoundary} from './ErrorBoundary';

function Bomb({shouldThrow = true}: {shouldThrow?: boolean}) {
  if (shouldThrow) {
    throw new Error('boom');
  }
  return <div>safe child</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary fallback={<div>fallback</div>}>
        <div>happy child</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('happy child')).toBeInTheDocument();
    expect(screen.queryByText('fallback')).not.toBeInTheDocument();
  });

  it('renders fallback when a child throws', () => {
    render(
      <ErrorBoundary fallback={<div>fallback</div>}>
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText('fallback')).toBeInTheDocument();
  });

  it('stays in error state when resetKeys do not change between renders', () => {
    const {rerender} = render(
      <ErrorBoundary fallback={<div>fallback</div>} resetKeys={['a']}>
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText('fallback')).toBeInTheDocument();

    rerender(
      <ErrorBoundary fallback={<div>fallback</div>} resetKeys={['a']}>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('fallback')).toBeInTheDocument();
    expect(screen.queryByText('safe child')).not.toBeInTheDocument();
  });

  it('resets and re-renders children when resetKeys change', () => {
    const {rerender} = render(
      <ErrorBoundary fallback={<div>fallback</div>} resetKeys={['a']}>
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText('fallback')).toBeInTheDocument();

    rerender(
      <ErrorBoundary fallback={<div>fallback</div>} resetKeys={['b']}>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('safe child')).toBeInTheDocument();
    expect(screen.queryByText('fallback')).not.toBeInTheDocument();
  });

  it('resets when resetKeys length changes', () => {
    const {rerender} = render(
      <ErrorBoundary fallback={<div>fallback</div>} resetKeys={['a']}>
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText('fallback')).toBeInTheDocument();

    rerender(
      <ErrorBoundary fallback={<div>fallback</div>} resetKeys={['a', 'b']}>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('safe child')).toBeInTheDocument();
  });
});
