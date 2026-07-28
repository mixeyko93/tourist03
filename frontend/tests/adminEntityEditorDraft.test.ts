import assert from "node:assert/strict";
import test from "node:test";

import {
  contactFieldsFromSnapshot,
  mergeEditorContacts,
  priceModeAfterAmountChange,
  priceModeFromApi,
} from "../src/crm/admin/entityEditorDraft.ts";
import type { SuperadminPlaceContact } from "../src/crm/admin/session.ts";

test("superadmin contact draft preserves custom, private and extra contacts", () => {
  const snapshot: SuperadminPlaceContact[] = [
    { id: 1, contact_type: "phone", label: "Основной", value: "+79990000001", is_public: true, sort_order: 10 },
    { id: 2, contact_type: "phone", label: "Запасной", value: "+79990000002", is_public: true, sort_order: 20 },
    { id: 3, contact_type: "phone", label: "Третий телефон", value: "+79990000003", is_public: true, sort_order: 30 },
    { id: 4, contact_type: "route", label: "Как добраться", value: "Маршрут", public_url: "https://maps.example.org/route", is_public: true, sort_order: 40 },
    { id: 5, contact_type: "other", label: "Связаться", value: "https://example.org/contact", is_public: true, sort_order: 50 },
    { id: 6, contact_type: "email", label: "Служебный", value: "private@example.org", is_public: false, sort_order: 60 },
  ];
  const fields = contactFieldsFromSnapshot(snapshot);
  assert.equal(fields.routeUrl, "https://maps.example.org/route");

  const merged = mergeEditorContacts(snapshot, {
    ...fields,
    publicPhoneSecondary: "",
    routeUrl: "https://maps.example.org/new-route",
  });

  assert.equal(merged.some((contact) => contact.id === 2), false);
  assert.equal(merged.find((contact) => contact.id === 3)?.value, "+79990000003");
  assert.equal(merged.find((contact) => contact.id === 5)?.label, "Связаться");
  assert.equal(merged.find((contact) => contact.id === 6)?.is_public, false);
  const route = merged.find((contact) => contact.id === 4);
  assert.equal(route?.value, "https://maps.example.org/new-route");
  assert.equal(route?.public_url, undefined);
  assert.equal(route?.label, "Как добраться");
});

test("new positive price defaults to from while API values remain explicit", () => {
  assert.equal(priceModeAfterAmountChange("none", 2500, true), "from");
  assert.equal(priceModeAfterAmountChange("none", null, true), "none");
  assert.equal(priceModeAfterAmountChange("fixed", 2500, true), "fixed");
  assert.equal(priceModeAfterAmountChange("none", 2500, false), "none");
  assert.equal(priceModeFromApi(null, 2500), "from");
  assert.equal(priceModeFromApi("none", 2500), "none");
});
