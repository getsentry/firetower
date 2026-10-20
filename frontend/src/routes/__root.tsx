import * as stylex from '@stylexjs/stylex';
import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext, Outlet} from '@tanstack/react-router';
import {TanStackRouterDevtools} from '@tanstack/react-router-devtools';
import {ErrorState} from 'components/ErrorState';
import {TooltipProvider} from 'components/Tooltip';

import {background, content, lineHeight, space} from '../styles/tokens.stylex';

import {Header} from './components/Header';

const RootLayout = () => (
  <TooltipProvider delayDuration={200}>
    <div {...stylex.props(styles.page)}>
      <Header />
      <main {...stylex.props(styles.main)}>
        <Outlet />
      </main>
      <TanStackRouterDevtools />
    </div>
  </TooltipProvider>
);

export const Route = createRootRouteWithContext<{queryClient: QueryClient}>()({
  component: RootLayout,
  notFoundComponent: () => <ErrorState title="Page not found" showBackButton />,
});

const styles = stylex.create({
  page: {
    backgroundColor: background.tertiary,
    color: content.primary,
    lineHeight: lineHeight.default,
    minHeight: '100vh',
  },
  main: {
    paddingInline: {default: space.md, '@media (min-width: 768px)': space.lg},
    paddingBlock: space.lg,
    marginInline: 'auto',
    maxWidth: 1152,
  },
});
