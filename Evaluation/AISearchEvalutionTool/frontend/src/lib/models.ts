// Shared model "library" — the single source of truth for the model picker used
// across every page (LLM Config, Prompts, …). Keep model lists here, not in pages.

export const CLAUDE_MODELS = [
  "claude-opus-4-7",
  "claude-sonnet-4-6",
  "claude-haiku-4-5-20251001",
];

export const OPENAI_MODELS = [
  "gpt-4.1",
  "gpt-4.1-mini",
  "gpt-4o",
  "gpt-4o-mini",
  "gpt-5",
  "gpt-5-mini",
  "o3",
  "o3-mini",
  "o4-mini",
];

export const GEMINI_MODELS = [
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "gemini-1.5-pro",
  "gemini-1.5-flash",
];

// Sentinel <select> values — NOT real model IDs. "Azure" and "Custom" both reveal
// a free-text deployment/model input; Azure additionally points the user at the
// API Keys page, since Azure routing is driven by the OpenAI base URL (endpoint),
// not the model name.
export const AZURE_VALUE = "__azure__";
export const CUSTOM_VALUE = "__custom__";
// Per-agent picker: inherit the app-wide default model configured on API Keys.
// Stored as an empty model string; the backend resolves it to default_model.
export const INHERIT_VALUE = "__inherit__";

// The literal model value that routes to the dedicated Azure OpenAI provider
// (endpoint / deployment / key / api-version configured on the API Keys page).
export const AZURE_MODEL = "azure";

export function isAzureModel(model: string): boolean {
  return model === AZURE_MODEL;
}

export function isClaudeModel(model: string): boolean {
  return CLAUDE_MODELS.includes(model);
}

export function isGeminiModel(model: string): boolean {
  return (
    GEMINI_MODELS.includes(model) ||
    model.startsWith("gemini-") ||
    model.startsWith("models/gemini-")
  );
}

export function isKnownModel(model: string): boolean {
  return (
    CLAUDE_MODELS.includes(model) ||
    OPENAI_MODELS.includes(model) ||
    GEMINI_MODELS.includes(model)
  );
}

// Short provider label shown next to the picker.
export function providerLabel(model: string): string {
  if (isAzureModel(model)) return "Azure OpenAI";
  if (isClaudeModel(model)) return "Anthropic";
  if (isGeminiModel(model)) return "Gemini";
  return "OpenAI";
}
