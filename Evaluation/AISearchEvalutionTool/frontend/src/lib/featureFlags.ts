/** Compile-time feature flags.
 *
 * Flip to `true` to re-enable. Each flag is independently consumed at the
 * relevant render site (no global wiring), so toggling one doesn't affect
 * other parts of the app.
 *
 * Backend code, routes, DB columns, and prompts for disabled features are
 * intentionally left in place — flipping the flag back on requires no
 * migration.
 */
export const FEATURE_AI_DEEP_DIVE = false;
