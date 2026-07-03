import {render} from '@testing-library/react';
import {TooltipProvider} from 'components/Tooltip';
import {describe, expect, it} from 'vitest';

import {PriorityIcon} from './PriorityIcon';

function renderWithProvider(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('PriorityIcon', () => {
  it('renders nothing for priority 0', () => {
    const {container} = renderWithProvider(<PriorityIcon priority={0} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('renders nothing for unknown priority', () => {
    const {container} = renderWithProvider(<PriorityIcon priority={5} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('renders an svg for priority 1 (Urgent)', () => {
    const {container} = renderWithProvider(<PriorityIcon priority={1} />);
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders an svg for priority 2 (High)', () => {
    const {container} = renderWithProvider(<PriorityIcon priority={2} />);
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders an svg for priority 3 (Medium)', () => {
    const {container} = renderWithProvider(<PriorityIcon priority={3} />);
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders an svg for priority 4 (Low)', () => {
    const {container} = renderWithProvider(<PriorityIcon priority={4} />);
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders a tooltip trigger for valid priorities', () => {
    renderWithProvider(<PriorityIcon priority={1} />);
    // Radix Tooltip wires aria-describedby/data-state on the trigger element.
    const trigger = document.querySelector('[data-state]');
    expect(trigger).not.toBeNull();
  });
});
