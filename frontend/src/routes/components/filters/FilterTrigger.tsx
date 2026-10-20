import * as stylex from '@stylexjs/stylex';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {SlidersHorizontalIcon} from 'lucide-react';

import {
  background,
  content,
  fontSize,
  radius,
  space,
} from '../../../styles/tokens.stylex';
import {useActiveFilters} from '../useActiveFilters';

export function FilterTrigger({open, onToggle}: {open: boolean; onToggle: () => void}) {
  const navigate = useNavigate({from: '/'});
  const {activeCount} = useActiveFilters();

  return (
    <div {...stylex.props(styles.container)}>
      {activeCount > 0 ? (
        <button
          type="button"
          {...stylex.props(styles.clear)}
          onClick={() => {
            navigate({
              to: '/',
              search: prev => ({status: prev.status}),
              replace: true,
            });
          }}
          data-testid="clear-all-filters"
        >
          Clear all filters
        </button>
      ) : null}
      <Button
        variant="secondary"
        size="sm"
        onClick={onToggle}
        aria-expanded={open}
        data-testid="advanced-filters-toggle"
      >
        <SlidersHorizontalIcon {...stylex.props(styles.icon)} />
        {open ? 'Hide filters' : 'Show filters'}
        {activeCount > 0 ? (
          <span {...stylex.props(styles.count)}>{activeCount}</span>
        ) : null}
      </Button>
    </div>
  );
}

const styles = stylex.create({
  container: {gap: space.md, display: 'flex', alignItems: 'center'},
  clear: {
    color: content.accent,
    fontSize: fontSize.sm,
    cursor: 'pointer',
    textDecoration: {default: null, ':hover': 'underline'},
  },
  icon: {height: 14, width: 14},
  count: {
    backgroundColor: background.accentVibrant,
    color: content.onVibrantLight,
    marginLeft: space['2xs'],
    display: 'inline-flex',
    height: 16,
    minWidth: 16,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.full,
    paddingInline: 4,
    fontSize: 12,
    lineHeight: 1,
  },
});
