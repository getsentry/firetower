import {createRef} from 'react';
import * as stylex from '@stylexjs/stylex';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, vi} from 'vitest';

import {Button} from './Button';

const styles = stylex.create({height: (height: number) => ({height})});

describe('Button', () => {
  it('forwards native events, refs, and caller styles', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const ref = createRef<HTMLButtonElement>();
    render(
      <Button ref={ref} onClick={onClick} style={styles.height(44)}>
        Save
      </Button>
    );
    const button = screen.getByRole('button', {name: 'Save'});
    expect(ref.current).toBe(button);
    expect(button).toHaveAttribute('type', 'button');
    expect(button.getAttribute('style')).toContain('44px');
    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('disables activation while loading and replaces content with an accessible status', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} loading>
        Save
      </Button>
    );
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(screen.getByRole('status', {name: 'Loading'})).toBeInTheDocument();
    expect(screen.queryByText('Save')).not.toBeInTheDocument();
    await user.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
