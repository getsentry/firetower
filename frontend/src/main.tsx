import {StrictMode} from 'react';
import ReactDOM from 'react-dom/client';
import * as Sentry from '@sentry/react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {createRouter, RouterProvider} from '@tanstack/react-router';

import {routeTree} from './routeTree.gen';

if (import.meta.env.MODE != 'development') {
  Sentry.init({
    dsn: 'https://82cb16514b69a48430dc945408138e0d@o1.ingest.us.sentry.io/4510076293283840',
    sendDefaultPii: false,
    environment: String(import.meta.env.MODE),
    integrations: [
      Sentry.feedbackIntegration({
        colorScheme: 'system',
      }),
    ],
  });
}

const queryClient = new QueryClient();
const router = createRouter({
  routeTree,
  context: {
    queryClient,
  },
  Wrap: ({children}) => {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  },
  defaultErrorComponent: () => <p>Error</p>,
  defaultPendingComponent: () => <p>Loading</p>,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

const rootElement = document.getElementById('root')!;
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement, {
    onUncaughtError: Sentry.reactErrorHandler((error, errorInfo) => {
      console.warn('Uncaught error', error, errorInfo.componentStack);
    }),
    // Callback called when React catches an error in an ErrorBoundary.
    onCaughtError: Sentry.reactErrorHandler(),
    // Callback called when React automatically recovers from errors.
    onRecoverableError: Sentry.reactErrorHandler(),
  });
  root.render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>
  );
}
