import type { SuperadminPlaceContact } from "./session";

export type AdminPriceMode = "from" | "fixed" | "request" | "free" | "none";

export type EditorContactFields = {
  publicEmail: string;
  publicPhone: string;
  publicPhoneSecondary: string;
  publicSite: string;
  telegramUrl: string;
  whatsappUrl: string;
  maxUrl: string;
  vkUrl: string;
  routeUrl: string;
};

type ContactSlot = {
  field: keyof EditorContactFields;
  contactType: SuperadminPlaceContact["contact_type"];
  index: number;
  label: string;
  sortOrder: number;
  usesUrl: boolean;
};

const CONTACT_SLOTS: ContactSlot[] = [
  { field: "publicPhone", contactType: "phone", index: 0, label: "Телефон", sortOrder: 10, usesUrl: false },
  { field: "publicPhoneSecondary", contactType: "phone", index: 1, label: "Дополнительный телефон", sortOrder: 20, usesUrl: false },
  { field: "publicEmail", contactType: "email", index: 0, label: "Email", sortOrder: 30, usesUrl: false },
  { field: "publicSite", contactType: "website", index: 0, label: "Сайт", sortOrder: 40, usesUrl: true },
  { field: "telegramUrl", contactType: "telegram", index: 0, label: "Telegram", sortOrder: 50, usesUrl: true },
  { field: "whatsappUrl", contactType: "whatsapp", index: 0, label: "WhatsApp", sortOrder: 60, usesUrl: true },
  { field: "maxUrl", contactType: "max", index: 0, label: "MAX", sortOrder: 70, usesUrl: true },
  { field: "vkUrl", contactType: "vk", index: 0, label: "ВКонтакте", sortOrder: 80, usesUrl: true },
  { field: "routeUrl", contactType: "route", index: 0, label: "Маршрут", sortOrder: 90, usesUrl: true },
];

function publicContactsOfType(
  contacts: SuperadminPlaceContact[],
  contactType: SuperadminPlaceContact["contact_type"],
) {
  return contacts.filter((contact) => contact.contact_type === contactType && contact.is_public !== false);
}

function editableContactValue(contact: SuperadminPlaceContact | undefined, usesUrl: boolean) {
  if (!contact) return "";
  return (usesUrl ? contact.public_url || contact.value : contact.value) || "";
}

export function contactFieldsFromSnapshot(contacts: SuperadminPlaceContact[]): EditorContactFields {
  return Object.fromEntries(
    CONTACT_SLOTS.map((slot) => [
      slot.field,
      editableContactValue(publicContactsOfType(contacts, slot.contactType)[slot.index], slot.usesUrl),
    ]),
  ) as EditorContactFields;
}

export function mergeEditorContacts(
  snapshot: SuperadminPlaceContact[],
  fields: EditorContactFields,
): SuperadminPlaceContact[] {
  const slotByContact = new Map<SuperadminPlaceContact, ContactSlot>();
  for (const slot of CONTACT_SLOTS) {
    const contact = publicContactsOfType(snapshot, slot.contactType)[slot.index];
    if (contact) slotByContact.set(contact, slot);
  }

  const merged = snapshot.flatMap((contact) => {
    const slot = slotByContact.get(contact);
    if (!slot) {
      return [{ ...contact }];
    }
    const nextValue = fields[slot.field].trim();
    if (!nextValue) {
      return [];
    }
    if (nextValue === editableContactValue(contact, slot.usesUrl).trim()) {
      return [{ ...contact }];
    }
    return [{
      ...contact,
      value: nextValue,
      // The server derives and validates the URL from the changed value.
      // Keeping the previous URL here would make an edited contact point to
      // the stale destination.
      public_url: undefined,
    }];
  });

  for (const slot of CONTACT_SLOTS) {
    const existing = publicContactsOfType(snapshot, slot.contactType)[slot.index];
    const value = fields[slot.field].trim();
    if (!existing && value) {
      merged.push({
        contact_type: slot.contactType,
        label: slot.label,
        value,
        is_public: true,
        sort_order: slot.sortOrder,
      });
    }
  }
  return merged;
}

export function priceModeAfterAmountChange(
  current: AdminPriceMode,
  amount: number | null,
  isNew: boolean,
): AdminPriceMode {
  return isNew && current === "none" && amount != null && amount > 0 ? "from" : current;
}

export function priceModeFromApi(value: string | null | undefined, minPrice: number | null | undefined): AdminPriceMode {
  if (value === "from" || value === "fixed" || value === "request" || value === "free" || value === "none") {
    return value;
  }
  return minPrice != null && minPrice > 0 ? "from" : "none";
}
