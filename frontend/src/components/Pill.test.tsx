import React from 'react';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, vi} from 'vitest';

import {Pill} from './Pill';

describe('Pill', () => {
  it('renders children', () => {
    render(<Pill>Test Pill</Pill>);
    expect(screen.getByText('Test Pill')).toBeInTheDocument();
  });

  it('accepts inline styles', () => {
    render(<Pill style={{paddingInline: 20}}>Styled</Pill>);
    expect(screen.getByText('Styled').style.paddingInline).toBe('20px');
  });

  it('forwards click handlers', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Pill onClick={onClick}>Clickable</Pill>);

    await user.click(screen.getByText('Clickable'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('accepts custom className', () => {
    render(
      <Pill className="custom-class" data-testid="pill">
        Custom
      </Pill>
    );
    const pill = screen.getByTestId('pill');

    expect(pill).toHaveClass('custom-class');
  });

  it('forwards ref', () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<Pill ref={ref}>Ref Test</Pill>);

    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });

  it('spreads additional props', () => {
    render(
      <Pill data-custom="test" data-testid="pill">
        Props Test
      </Pill>
    );
    const pill = screen.getByTestId('pill');

    expect(pill).toHaveAttribute('data-custom', 'test');
  });
});
