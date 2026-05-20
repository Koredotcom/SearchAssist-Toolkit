import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { appsApi } from "@/lib/api";
import type { AppConfig, AppConfigCreate } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Plus, Pencil, Trash2, Bot, CheckCircle, XCircle, ExternalLink, Info } from "lucide-react";

const EMPTY_FORM: AppConfigCreate & { app_id?: string } = {
  name: "",
  host_url: "",
  bot_id: "",
  stream_id: "",
  client_id: "",
  client_secret: "",
  racl_entity_ids: [],
  answer_mode: "answer_generation",
};

// Bot ID and Stream ID are always the same in Kore.ai SearchAI
const syncStreamId = (botId: string, current: string, prevBotId: string): string =>
  current === "" || current === prevBotId ? botId : current;

export default function AppsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<AppConfig | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [raclInput, setRaclInput] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ["apps"],
    queryFn: appsApi.list,
  });

  const createMutation = useMutation({
    mutationFn: appsApi.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["apps"] }); closeForm(); },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AppConfigCreate> }) =>
      appsApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["apps"] }); closeForm(); },
  });

  const deleteMutation = useMutation({
    mutationFn: appsApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["apps"] }); setDeleteConfirm(null); },
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setRaclInput("");
    setShowForm(true);
  }

  function openEdit(app: AppConfig) {
    setEditing(app);
    setForm({
      name: app.name,
      host_url: app.host_url,
      bot_id: app.bot_id,
      stream_id: app.stream_id ?? "",
      client_id: app.client_id,
      client_secret: "",
      racl_entity_ids: app.racl_entity_ids,
      answer_mode: app.answer_mode ?? "answer_generation",
    });
    setRaclInput(app.racl_entity_ids.join(", "));
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setRaclInput("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const racls = raclInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const payload = { ...form, racl_entity_ids: racls };
    if (editing) {
      const update: Partial<AppConfigCreate> = {
        name: payload.name,
        host_url: payload.host_url,
        bot_id: payload.bot_id,
        stream_id: payload.stream_id || payload.bot_id,
        client_id: payload.client_id,
        racl_entity_ids: racls,
        answer_mode: payload.answer_mode,
      };
      if (payload.client_secret) update.client_secret = payload.client_secret;
      updateMutation.mutate({ id: editing.app_id, data: update });
    } else {
      createMutation.mutate(payload);
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;
  const error = createMutation.error || updateMutation.error;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Apps</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your RAG application configurations</p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New App
        </button>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-gray-400">Loading apps...</div>
      )}

      {!isLoading && apps.length === 0 && !showForm && (
        <div className="text-center py-16 border-2 border-dashed border-gray-200 rounded-xl">
          <Bot className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No apps configured yet</p>
          <p className="text-gray-400 text-sm mt-1">Create your first app to get started</p>
          <button
            onClick={openCreate}
            className="mt-4 px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700"
          >
            Create App
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {apps.map((app) => (
          <AppCard
            key={app.app_id}
            app={app}
            onEdit={() => openEdit(app)}
            onDelete={() => setDeleteConfirm(app.app_id)}
            onOpen={() => navigate(`/apps/${app.app_id}/sources`)}
          />
        ))}
      </div>

      {/* Delete confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
            <h3 className="font-semibold text-gray-900 mb-2">Delete App?</h3>
            <p className="text-sm text-gray-500 mb-4">
              This will permanently delete the app and all associated data. This cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteConfirm)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit form modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">
                {editing ? "Edit App" : "New App"}
              </h2>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <Field label="App Name" required>
                <input
                  type="text"
                  required
                  placeholder="e.g. Code.ai Production"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={inputCls}
                />
              </Field>

              <Field label="Host URL" required hint="Kore.ai SearchAI base URL">
                <input
                  type="url"
                  required
                  placeholder="https://your-instance.kore.ai"
                  value={form.host_url}
                  onChange={(e) => setForm({ ...form, host_url: e.target.value })}
                  className={inputCls}
                />
              </Field>

              <Field label="Bot ID / Stream ID" required hint="Bot ID and Stream ID are the same in Kore.ai SearchAI — enter once">
                <input
                  type="text"
                  required
                  placeholder="st-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  value={form.bot_id}
                  onChange={(e) => {
                    const newBotId = e.target.value;
                    setForm({
                      ...form,
                      bot_id: newBotId,
                      stream_id: syncStreamId(newBotId, form.stream_id ?? "", form.bot_id),
                    });
                  }}
                  className={inputCls}
                />
                <p className="mt-1 flex items-center gap-1 text-xs text-blue-600">
                  <Info className="w-3 h-3" />
                  Stream ID is automatically set to the same value
                </p>
              </Field>

              <Field label="Client ID" required hint="Kore.ai app client ID (cs-…)">
                <input
                  type="text"
                  required
                  placeholder="cs-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  value={form.client_id}
                  onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                  className={inputCls}
                />
              </Field>

              <Field
                label="Client Secret"
                required={!editing}
                hint={editing ? "Leave blank to keep the existing secret (JWT will not be regenerated)" : "Used to generate the HS256 JWT automatically"}
              >
                <input
                  type="password"
                  required={!editing}
                  placeholder={editing ? "Leave blank to keep existing" : "Your Kore.ai client secret"}
                  value={form.client_secret}
                  onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                  className={inputCls}
                />
              </Field>

              {editing && (
                <Field label="RACL Entity IDs" hint="Comma-separated list of entity IDs for row-level access control">
                  <input
                    type="text"
                    placeholder="entity-id-1, entity-id-2"
                    value={raclInput}
                    onChange={(e) => setRaclInput(e.target.value)}
                    className={inputCls}
                  />
                </Field>
              )}

              {error && (
                <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
                  {(error as Error).message}
                </p>
              )}

              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={closeForm}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50"
                >
                  {isPending ? "Saving..." : editing ? "Save Changes" : "Create App"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function AppCard({
  app,
  onEdit,
  onDelete,
  onOpen,
}: {
  app: AppConfig;
  onEdit: () => void;
  onDelete: () => void;
  onOpen: () => void;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-2.5 h-2.5 rounded-full mt-0.5",
              app.is_active ? "bg-green-500" : "bg-gray-300"
            )}
          />
          <h3 className="font-semibold text-gray-900 text-sm">{app.name}</h3>
        </div>
        <div className="flex items-center gap-1">
          {app.is_active ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <XCircle className="w-4 h-4 text-gray-300" />
          )}
        </div>
      </div>

      <p className="text-xs text-gray-400 mb-1 truncate">{app.host_url}</p>
      <p className="text-xs text-gray-400 mb-1 font-mono truncate">{app.bot_id}</p>
      {app.client_id && (
        <p className="text-xs text-gray-400 mb-3 font-mono truncate">
          <span className="text-gray-300">client: </span>{app.client_id}
        </p>
      )}

      {app.racl_entity_ids.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {app.racl_entity_ids.slice(0, 3).map((id) => (
            <span
              key={id}
              className="text-xs px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full"
            >
              {id}
            </span>
          ))}
          {app.racl_entity_ids.length > 3 && (
            <span className="text-xs text-gray-400">+{app.racl_entity_ids.length - 3} more</span>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 pt-3 border-t border-gray-100">
        <button
          onClick={onOpen}
          className="flex items-center gap-1.5 flex-1 justify-center px-3 py-1.5 text-xs text-violet-600 hover:bg-violet-50 rounded-lg transition-colors"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Open
        </button>
        <button
          onClick={onEdit}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <Pencil className="w-3.5 h-3.5" />
          Edit
        </button>
        <button
          onClick={onDelete}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400 hover:bg-red-50 rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Delete
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

const inputCls =
  "w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent placeholder:text-gray-300";
