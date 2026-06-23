/**
 * Lightweight structured logger for the frontend.
 *
 * Every message gets a timestamp + level prefix. In production builds
 * DEBUG messages are suppressed; everything else still goes to the
 * browser console where DevTools can filter by level.
 *
 * Usage:
 *   import { logger } from "@/lib/logger";
 *   logger.info("EvaluatePage", "run started", { runId });
 *   logger.error("api", "request failed", { url, status, body });
 */

type Level = "DEBUG" | "INFO" | "WARN" | "ERROR";

const IS_DEV = import.meta.env.DEV;

function _ts(): string {
  return new Date().toISOString().replace("T", " ").slice(0, 23);
}

function _log(level: Level, context: string, message: string, data?: unknown): void {
  if (level === "DEBUG" && !IS_DEV) return;

  const prefix = `${_ts()} [${level.padEnd(5)}] ${context} —`;

  switch (level) {
    case "DEBUG": console.debug(prefix, message, ...(data !== undefined ? [data] : [])); break;
    case "INFO":  console.info (prefix, message, ...(data !== undefined ? [data] : [])); break;
    case "WARN":  console.warn (prefix, message, ...(data !== undefined ? [data] : [])); break;
    case "ERROR": console.error(prefix, message, ...(data !== undefined ? [data] : [])); break;
  }
}

export const logger = {
  debug: (ctx: string, msg: string, data?: unknown) => _log("DEBUG", ctx, msg, data),
  info:  (ctx: string, msg: string, data?: unknown) => _log("INFO",  ctx, msg, data),
  warn:  (ctx: string, msg: string, data?: unknown) => _log("WARN",  ctx, msg, data),
  error: (ctx: string, msg: string, data?: unknown) => _log("ERROR", ctx, msg, data),
};
