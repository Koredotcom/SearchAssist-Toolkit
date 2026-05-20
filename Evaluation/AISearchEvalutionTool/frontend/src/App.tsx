import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
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
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/apps" replace />} />
        <Route path="apps" element={<AppsPage />} />
        <Route path="apps/:appId/sources" element={<SourcesPage />} />
        <Route path="apps/:appId/generate" element={<GeneratePage />} />
        <Route path="apps/:appId/evaluate" element={<EvaluatePage />} />
        <Route path="apps/:appId/golden-sets" element={<GoldenSetsPage />} />
        <Route path="apps/:appId/prompts" element={<PromptsPage />} />
        <Route path="apps/:appId/llm" element={<LLMConfigPage />} />
        <Route path="apps/:appId/results" element={<ResultsPage />} />
        <Route path="apps/:appId/results/:runId" element={<RunDetailPage />} />
        <Route path="apps/:appId/api-keys" element={<AppApiKeysPage />} />
        {/* TODO: missing QueryPage — backend router (routers/query.py) and queryApi (lib/api.ts) are ready; need frontend/src/pages/QueryPage.tsx + route apps/:appId/query */}
      </Route>
    </Routes>
  );
}
