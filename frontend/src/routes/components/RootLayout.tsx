import * as stylex from '@stylexjs/stylex';
import {Outlet} from '@tanstack/react-router';
import {TanStackRouterDevtools} from '@tanstack/react-router-devtools';
import {TooltipProvider} from 'components/Tooltip';

import {background, content, lineHeight, space} from '../../styles/tokens.stylex';

import {Header} from './Header';

export const RootLayout = () => (
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
