import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Layout from "@/components/Layout";
import ErrorBoundary from "@/components/ErrorBoundary";
import AppsPage from "@/pages/AppsPage";
import SourcesPage from "@/pages/SourcesPage";
import GeneratePage from "@/pages/GeneratePage";
import EvaluatePage from "@/pages/EvaluatePage";
import GoldenSetsPage from "@/pages/GoldenSetsPage";
import PromptsPage from "@/pages/PromptsPage";
import LLMConfigPage from "@/pages/LLMConfigPage";
import ResultsPage from "@/pages/ResultsPage";
import RunDetailPage from "@/pages/RunDetailPage";
import AppApiKeysPage from "@/pages/AppApiKeysPage";

export default function App() {
  const { pathname } = useLocation();
  return (
    <ErrorBoundary context="app">
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/apps" replace />} />
          <Route path="apps" element={<ErrorBoundary context="AppsPage" resetKey={pathname}><AppsPage /></ErrorBoundary>} />
          <Route path="apps/:appId/sources" element={<ErrorBoundary context="SourcesPage" resetKey={pathname}><SourcesPage /></ErrorBoundary>} />
          <Route path="apps/:appId/generate" element={<ErrorBoundary context="GeneratePage" resetKey={pathname}><GeneratePage /></ErrorBoundary>} />
          <Route path="apps/:appId/evaluate" element={<ErrorBoundary context="EvaluatePage" resetKey={pathname}><EvaluatePage /></ErrorBoundary>} />
          <Route path="apps/:appId/golden-sets" element={<ErrorBoundary context="GoldenSetsPage" resetKey={pathname}><GoldenSetsPage /></ErrorBoundary>} />
          <Route path="apps/:appId/prompts" element={<ErrorBoundary context="PromptsPage" resetKey={pathname}><PromptsPage /></ErrorBoundary>} />
          <Route path="apps/:appId/llm" element={<ErrorBoundary context="LLMConfigPage" resetKey={pathname}><LLMConfigPage /></ErrorBoundary>} />
          <Route path="apps/:appId/results" element={<ErrorBoundary context="ResultsPage" resetKey={pathname}><ResultsPage /></ErrorBoundary>} />
          <Route path="apps/:appId/results/:runId" element={<ErrorBoundary context="RunDetailPage" resetKey={pathname}><RunDetailPage /></ErrorBoundary>} />
          <Route path="apps/:appId/api-keys" element={<ErrorBoundary context="AppApiKeysPage" resetKey={pathname}><AppApiKeysPage /></ErrorBoundary>} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
