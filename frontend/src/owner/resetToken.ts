export function ownerResetTokenFromLocation(search: string, hash: string) {
  const fragmentToken = new URLSearchParams(hash.replace(/^#/, "")).get("reset") || "";
  if (fragmentToken) return fragmentToken;
  return new URLSearchParams(search).get("token") || "";
}
