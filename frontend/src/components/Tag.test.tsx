import React from 'react';
import * as stylex from '@stylexjs/stylex';
import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';

import {Tag} from './Tag';

describe('Tag', () => {
  it('renders children', () => {
    render(<Tag>Test Tag</Tag>);
    expect(screen.getByText('Test Tag')).toBeInTheDocument();
  });

  it('composes caller styles and dynamic dimensions', () => {
    render(<Tag style={[styles.padding(12), styles.padding(20)]}>Styled</Tag>);
    expect(screen.getByText('Styled').parentElement?.getAttribute('style')).toContain(
      '20px'
    );
    expect(screen.getByText('Styled').parentElement?.getAttribute('style')).not.toContain(
      '12px'
    );
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

  it('wraps content in inner span', () => {
    render(<Tag data-testid="tag">Content</Tag>);
    const tag = screen.getByTestId('tag');
    const inner = tag.querySelector('span');

    expect(inner).toBeInTheDocument();
    expect(inner).toHaveTextContent('Content');
  });
});

const styles = stylex.create({padding: (value: number) => ({paddingInline: value})});
