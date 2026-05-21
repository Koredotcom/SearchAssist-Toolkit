import { useState } from "react";
import { Outlet, NavLink, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { appsApi } from "@/lib/api";
import type { AppConfig } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard, Database, Zap, FlaskConical, BookOpen,
  Settings2, BarChart3, ChevronDown, Plus, Bot, KeySquare
} from "lucide-react";

const appNavItems = (appId: string) => [
  { to: `/apps/${appId}/sources`,     label: "Sources",      icon: Database },
  { to: `/apps/${appId}/generate`,    label: "Generate",     icon: Zap },
  { to: `/apps/${appId}/golden-sets`, label: "Golden Sets",  icon: BookOpen },
  { to: `/apps/${appId}/evaluate`,    label: "Evaluate",     icon: FlaskConical },
  { to: `/apps/${appId}/results`,     label: "Results",      icon: BarChart3 },
  { to: `/apps/${appId}/prompts`,     label: "Prompts & Models", icon: Settings2 },
  { to: `/apps/${appId}/api-keys`,    label: "API Keys",     icon: KeySquare },
  // TODO: missing QueryPage — add { to: `/apps/${appId}/query`, label: "Query", icon: Search } once QueryPage.tsx is created
];

export default function Layout() {
  const { appId } = useParams<{ appId?: string }>();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { data: apps = [] } = useQuery({
    queryKey: ["apps"],
    queryFn: appsApi.list,
  });

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 overflow-hidden">
      {/* Sidebar */}
      <aside className={cn(
        "flex flex-col bg-white border-r border-gray-200 transition-all duration-200",
        sidebarOpen ? "w-64" : "w-16"
      )}>
        {/* Brand */}
        <div className="flex items-center gap-2 px-4 py-4 border-b border-gray-100">
          <Bot className="w-6 h-6 text-violet-600 shrink-0" />
          {sidebarOpen && (
            <span className="font-bold text-gray-900 text-sm">SearchAI Evaluation</span>
          )}
        </div>

        {/* Apps list */}
        <div className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
          {/* All apps link */}
          <NavLink
            to="/apps"
            className={({ isActive }) =>
              cn("flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive && !appId
                  ? "bg-violet-50 text-violet-700 font-medium"
                  : "text-gray-600 hover:bg-gray-100")
            }
          >
            <LayoutDashboard className="w-4 h-4 shrink-0" />
            {sidebarOpen && "All Apps"}
          </NavLink>

          {/* Per-app nav */}
          {apps.map((app) => (
            <AppNavGroup
              key={app.app_id}
              app={app}
              isSelected={app.app_id === appId}
              collapsed={!sidebarOpen}
            />
          ))}

          {/* Add app button */}
          <button
            onClick={() => navigate("/apps")}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-400 hover:text-violet-600 hover:bg-violet-50 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4 shrink-0" />
            {sidebarOpen && "Add App"}
          </button>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="flex items-center justify-center p-3 border-t border-gray-100 text-gray-400 hover:text-gray-700"
        >
          <ChevronDown className={cn("w-4 h-4 transition-transform", sidebarOpen ? "-rotate-90" : "rotate-90")} />
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function AppNavGroup({ app, isSelected, collapsed }: {
  app: AppConfig;
  isSelected: boolean;
  collapsed: boolean;
}) {
  const [open, setOpen] = useState(isSelected);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm transition-colors",
          isSelected ? "text-violet-700 font-medium" : "text-gray-700 hover:bg-gray-100"
        )}
      >
        <div className={cn(
          "w-2 h-2 rounded-full shrink-0",
          app.is_active ? "bg-green-500" : "bg-gray-300"
        )} />
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate">{app.name}</span>
            <ChevronDown className={cn("w-3 h-3 transition-transform", open && "rotate-180")} />
          </>
        )}
      </button>

      {open && !collapsed && (
        <div className="ml-4 mt-1 space-y-0.5 border-l border-gray-100 pl-3">
          {appNavItems(app.app_id).map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn("flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors",
                  isActive
                    ? "bg-violet-50 text-violet-700 font-medium"
                    : "text-gray-500 hover:text-gray-900 hover:bg-gray-50")
              }
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              {label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}
