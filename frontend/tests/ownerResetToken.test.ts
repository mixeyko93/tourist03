import assert from "node:assert/strict";
import test from "node:test";

import { ownerResetTokenFromLocation } from "../src/owner/resetToken.ts";


test("owner password reset token is read from a non-leaking URL fragment", () => {
  assert.equal(
    ownerResetTokenFromLocation("", "#reset=safe-token%2Fvalue"),
    "safe-token/value",
  );
});

test("legacy query token remains compatible and fragment takes precedence", () => {
  assert.equal(ownerResetTokenFromLocation("?token=legacy", ""), "legacy");
  assert.equal(
    ownerResetTokenFromLocation("?token=legacy", "#reset=current"),
    "current",
  );
});
