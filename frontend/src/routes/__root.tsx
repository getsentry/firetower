import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext} from '@tanstack/react-router';
import {ErrorState} from 'components/ErrorState';

import {RootLayout} from './components/RootLayout';

export const Route = createRootRouteWithContext<{queryClient: QueryClient}>()({
  component: RootLayout,
  notFoundComponent: () => <ErrorState title="Page not found" showBackButton />,
});
