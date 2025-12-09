import React from 'react';
import {render, screen} from '@testing-library/react';

import {Tag} from './Tag';

describe('Tag', () => {
  it('renders children', () => {
    render(<Tag>Test Tag</Tag>);
    expect(screen.getByText('Test Tag')).toBeInTheDocument();
  });

  it('applies base classes', () => {
    render(<Tag data-testid="tag">Default</Tag>);
    const tag = screen.getByTestId('tag');

    expect(tag).toHaveClass('bg-background-tertiary');
    expect(tag).toHaveClass('text-content-secondary');
    expect(tag).toHaveClass('px-space-md');
    expect(tag).toHaveClass('py-space-xs');
    expect(tag).toHaveClass('rounded-radius-xs');
    expect(tag).toHaveClass('text-size-sm');
  });

  it('accepts custom className', () => {
    render(
      <Tag className="custom-class" data-testid="tag">
        Custom
      </Tag>
    );
    const tag = screen.getByTestId('tag');

    expect(tag).toHaveClass('custom-class');
  });

  it('spreads additional props', () => {
    render(
      <Tag data-custom="test" data-testid="tag">
        Props Test
      </Tag>
    );
    const tag = screen.getByTestId('tag');

    expect(tag).toHaveAttribute('data-custom', 'test');
  });

  it('wraps content in span with margin fix', () => {
    render(<Tag data-testid="tag">Content</Tag>);
    const tag = screen.getByTestId('tag');
    const inner = tag.querySelector('span');

    expect(inner).toBeInTheDocument();
    expect(inner).toHaveClass('mt-[2px]');
    expect(inner).toHaveClass('mb-auto');
  });
});
