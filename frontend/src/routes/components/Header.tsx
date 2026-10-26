import * as stylex from '@stylexjs/stylex';
import {useQuery} from '@tanstack/react-query';
import {Link, useRouterState} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';

import {
  background,
  border,
  content,
  fontSize,
  fontWeight,
  radius,
  space,
} from '../../styles/tokens.stylex';
import {currentUserQueryOptions} from '../queries/currentUserQueryOptions';
import type {StatusFilterValue} from '../types';

const STORAGE_KEY = 'firetower_list_search';

const NAV_PAGES = [
  {label: 'Incidents', to: '/' as const},
  {label: 'Availability', to: '/availability' as const},
];

export const Header = () => {
  const routerState = useRouterState();
  const {data: currentUser} = useQuery(currentUserQueryOptions());
  const pathname = routerState.location.pathname;

  const isActivePage = (to: string) =>
    pathname === to || (to !== '/' && pathname === `${to}/`);

  const isTopLevelRoute = NAV_PAGES.some(page => isActivePage(page.to));

  const getPreservedSearch = (): {status?: StatusFilterValue[]} | undefined => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return undefined;
      }
    }
    return undefined;
  };

  const preservedSearch = getPreservedSearch();

  return (
    <header {...stylex.props(styles.header)}>
      <div {...stylex.props(styles.container)}>
        {isTopLevelRoute ? (
          <div {...stylex.props(styles.row)}>
            <nav {...stylex.props(styles.navigation)}>
              {NAV_PAGES.map(page => (
                <Link
                  key={page.to}
                  to={page.to}
                  preload="intent"
                  {...stylex.props(
                    styles.navLink,
                    isActivePage(page.to) ? styles.activeLink : styles.inactiveLink
                  )}
                >
                  {page.label}
                </Link>
              ))}
            </nav>
            <Link to="/" {...stylex.props(styles.brand)}>
              <img src="/firetower.svg" alt="Firetower" {...stylex.props(styles.logo)} />
              <span {...stylex.props(styles.name)}>Firetower</span>
            </Link>
            {currentUser ? (
              <Avatar name={currentUser.name} src={currentUser.avatar_url} size="sm" />
            ) : (
              <div {...stylex.props(styles.avatarPlaceholder)} />
            )}
          </div>
        ) : (
          <div {...stylex.props(styles.row)}>
            <Link to="/" search={preservedSearch} {...stylex.props(styles.backLink)}>
              <span>←</span>
              <span>All Incidents</span>
            </Link>
            <Link to="/" {...stylex.props(styles.brand)}>
              <img src="/firetower.svg" alt="Firetower" {...stylex.props(styles.logo)} />
              <span {...stylex.props(styles.name)}>Firetower</span>
            </Link>
            {currentUser ? (
              <Avatar name={currentUser.name} src={currentUser.avatar_url} size="sm" />
            ) : (
              <div {...stylex.props(styles.avatarPlaceholder)} />
            )}
          </div>
        )}
      </div>
    </header>
  );
};

const styles = stylex.create({
  header: {
    backgroundColor: background.primary,
    borderColor: border.secondary,
    borderBottomWidth: 1,
    borderBottomStyle: 'solid',
  },
  container: {
    paddingInline: {default: space.md, '@media (min-width: 768px)': space.lg},
    paddingBlock: space.md,
    marginInline: 'auto',
    maxWidth: 1152,
  },
  row: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  navigation: {gap: space['2xs'], display: 'flex'},
  brand: {
    gap: space.sm,
    position: 'absolute',
    left: '50%',
    display: 'flex',
    transform: 'translateX(-50%)',
    alignItems: 'center',
    textDecoration: 'none',
  },
  logo: {height: 24, width: 24},
  name: {color: content.headings, fontSize: 20, lineHeight: '28px', fontWeight: 600},
  avatarPlaceholder: {height: 28, width: 28},
  backLink: {
    color: {default: content.secondary, ':hover': content.accent},
    backgroundColor: {default: null, ':hover': background.secondary},
    paddingInline: space.md,
    paddingBlock: space.sm,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    borderRadius: 2,
    fontSize: 12,
    lineHeight: '16px',
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
  navLink: {
    borderRadius: radius.sm,
    paddingInline: space.lg,
    paddingBlock: space.sm,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
  activeLink: {
    backgroundColor: {
      default: background.secondary,
      ':hover': background.transparentNeutralMuted,
    },
    color: content.headings,
  },
  inactiveLink: {
    color: {default: content.secondary, ':hover': content.headings},
    backgroundColor: {default: null, ':hover': background.transparentNeutralMuted},
  },
});
