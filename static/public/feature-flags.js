const defaults = Object.freeze({
  public_booking: false,
  public_user_auth: false,
  telegram_webapp: false,
  placement_submissions: false,
});

export function publicFeatures() {
  const runtimeFeatures = typeof window !== "undefined" ? window.__TOURISTIKA_FEATURES__ : undefined;
  return { ...defaults, ...(runtimeFeatures && typeof runtimeFeatures === "object" ? runtimeFeatures : {}) };
}
