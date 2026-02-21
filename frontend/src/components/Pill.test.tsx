import React from 'react';
import {render, screen} from '@testing-library/react';

import {Pill} from './Pill';

describe('Pill', () => {
  it('renders children', () => {
    render(<Pill>Test Pill</Pill>);
    expect(screen.getByText('Test Pill')).toBeInTheDocument();
  });

  it('applies default variant', () => {
    render(<Pill data-testid="pill">Default</Pill>);
    const pill = screen.getByTestId('pill');

    expect(pill).toHaveClass('bg-background-secondary');
    expect(pill).toHaveClass('text-content-secondary');
    expect(pill).toHaveClass('px-space-lg');
    expect(pill).toHaveClass('py-space-xs');
  });

  it('applies variant classes', () => {
    render(
      <Pill variant="Active" data-testid="pill">
        Active
      </Pill>
    );
    const pill = screen.getByTestId('pill');

    expect(pill).toHaveClass('bg-background-transparent-danger-muted');
    expect(pill).toHaveClass('text-content-danger');
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
