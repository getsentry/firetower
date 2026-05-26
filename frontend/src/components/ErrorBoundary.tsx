import {Component, type ErrorInfo, type ReactNode} from 'react';

interface ErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
  resetKeys?: ReadonlyArray<unknown>;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {hasError: false};
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return {hasError: true};
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (!this.state.hasError) {
      return;
    }
    const prevKeys = prevProps.resetKeys ?? [];
    const nextKeys = this.props.resetKeys ?? [];
    if (
      prevKeys.length !== nextKeys.length ||
      prevKeys.some((key, i) => key !== nextKeys[i])
    ) {
      this.setState({hasError: false});
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }

    return this.props.children;
  }
}
