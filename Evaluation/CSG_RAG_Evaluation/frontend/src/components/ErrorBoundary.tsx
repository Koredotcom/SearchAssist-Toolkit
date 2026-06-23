import { Component, type ErrorInfo, type ReactNode } from "react";
import { logger } from "@/lib/logger";

interface Props {
  children: ReactNode;
  /** Label shown in the fallback UI and log output (e.g. page name) */
  context?: string;
  /** When this value changes (e.g. current pathname) the error state is cleared */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prevProps: Props): void {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    const ctx = this.props.context ?? "app";
    logger.error(ctx, `Unhandled render error: ${error.message}`, {
      stack: error.stack,
      componentStack: info.componentStack,
    });
  }

  render() {
    if (this.state.error) {
      const ctx = this.props.context ?? "page";
      return (
        <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 p-8">
          <div className="text-red-500 text-4xl">⚠</div>
          <h2 className="text-lg font-semibold text-gray-800">Something went wrong in {ctx}</h2>
          <p className="text-sm text-gray-500 max-w-md text-center">
            {this.state.error.message}
          </p>
          <p className="text-xs text-gray-400">Check the browser console for the full stack trace.</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
