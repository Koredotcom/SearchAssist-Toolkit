import { useEffect } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ConfirmDialogProps {
  /** Controls visibility. When false, nothing renders. */
  open: boolean;
  /** Dialog heading. */
  title: string;
  /** Body description shown under the heading. */
  description?: React.ReactNode;
  /** Optional extra content (e.g. impact preview list) shown below the description. */
  children?: React.ReactNode;
  /** Label for the destructive action button (default: "Delete"). */
  confirmLabel?: string;
  /** Label for the cancel button (default: "Cancel"). */
  cancelLabel?: string;
  /** Visual tone — destructive shows red button + warning icon. */
  tone?: "destructive" | "default";
  /** Disables buttons + shows spinner on the confirm button. */
  loading?: boolean;
  /** Optional error message shown above the buttons. */
  error?: string | null;
  /** Called when the user clicks Cancel, presses Esc, or clicks the backdrop. */
  onCancel: () => void;
  /** Called when the user clicks the confirm button. */
  onConfirm: () => void;
}

export default function ConfirmDialog({
  open, title, description, children,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  tone = "destructive",
  loading = false,
  error = null,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, loading, onCancel]);

  if (!open) return null;

  const destructive = tone === "destructive";

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-[60] p-4"
      onClick={() => !loading && onCancel()}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 px-5 pt-5">
          <div className={cn(
            "w-9 h-9 shrink-0 rounded-full flex items-center justify-center",
            destructive ? "bg-red-100 text-red-600" : "bg-violet-100 text-violet-600"
          )}>
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">{title}</h3>
            {description && (
              <div className="text-sm text-gray-600 leading-relaxed">{description}</div>
            )}
          </div>
          <button
            onClick={() => !loading && onCancel()}
            className="text-gray-400 hover:text-gray-600 shrink-0"
            disabled={loading}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {children && (
          <div className="px-5 mt-3 mb-1">
            {children}
          </div>
        )}

        {error && (
          <div className="mx-5 my-3 p-2.5 border border-red-200 bg-red-50 rounded-md text-xs text-red-700">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 px-5 py-4 mt-2 border-t border-gray-100 bg-gray-50/50 rounded-b-xl">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-3.5 py-1.5 text-sm text-gray-700 rounded-md hover:bg-gray-100 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "flex items-center gap-1.5 px-3.5 py-1.5 text-sm font-medium text-white rounded-md disabled:opacity-60",
              destructive
                ? "bg-red-600 hover:bg-red-700"
                : "bg-violet-600 hover:bg-violet-700"
            )}
          >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {loading ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
