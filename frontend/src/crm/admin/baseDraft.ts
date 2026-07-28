import type { AdminPriceMode } from "./entityEditorDraft";
import type { SuperadminPlaceContact } from "./session";

export type AdminBaseStatus = "Активный" | "Отключен" | "В архиве";
export type AdminPublicationStatus = "draft" | "in_review" | "published" | "disabled" | "archived" | "rejected";

export type AdminBaseApartment = {
  id: string;
  unitType: string;
  name: string;
  guests: string;
  singleBeds: string;
  doubleBeds: string;
  shower: string;
  bbq: string;
  sauna: string;
  pool: string;
  conditioner: string;
  description: string;
  weekdayPrice: string;
  weekendPrice: string;
  extraGuestPrice: string;
  quantity: string;
  bookingWindow: string;
  photos: string[];
  videoUrl: string;
  videoPosterUrl: string;
  videoSourceKind: "upload" | "external";
};

export type AdminBaseDraft = {
  id: string;
  status: AdminBaseStatus;
  name: string;
  slug: string;
  placeTypeId: string;
  publicationStatus: AdminPublicationStatus;
  shortDescription: string;
  attributes: Record<string, unknown>;
  region: string;
  district: string;
  city: string;
  locality: string;
  seasonality: string;
  workingHours: string;
  confirmedAt: string;
  publicEmail: string;
  publicPhone: string;
  publicPhoneSecondary: string;
  publicSite: string;
  telegramUrl: string;
  whatsappUrl: string;
  maxUrl: string;
  vkUrl: string;
  routeUrl: string;
  contactsSnapshot: SuperadminPlaceContact[];
  videoLinks: string;
  amenitySlugs: string[];
  coverPlaceholderConfirmed: boolean;
  lake: string;
  coordinates: string;
  address: string;
  ownerName: string;
  ownerPhone: string;
  managerName: string;
  managerPhone: string;
  adminPhones: string[];
  site: string;
  accommodationType: string;
  apartmentCount: string;
  beds: string;
  bbqPrivate: string;
  bbqShared: string;
  baths: string;
  poolsPrivate: string;
  poolsShared: string;
  saunas: string;
  markerSize: "Стандарт" | "VIP";
  markerIcon: "tent" | "house" | "trees" | "waves" | "ship";
  description: string;
  minPrice: string;
  priceMode: AdminPriceMode;
  currency: string;
  gallery: string[];
  videoUrl: string;
  videoPosterUrl: string;
  videoSourceKind: "upload" | "external";
  apartments: AdminBaseApartment[];
};

export function createEmptyApartment(index: number): AdminBaseApartment {
  return {
    id: `new-apt-${index}`,
    unitType: "Апартамент",
    name: "",
    guests: "2",
    singleBeds: "0",
    doubleBeds: "1",
    shower: "Душ общий",
    bbq: "Общий",
    sauna: "Общая",
    pool: "Бассейн — нет",
    conditioner: "Кондиционер — нет",
    description: "",
    weekdayPrice: "0",
    weekendPrice: "0",
    extraGuestPrice: "0",
    quantity: "1",
    bookingWindow: "3",
    photos: [],
    videoUrl: "",
    videoPosterUrl: "",
    videoSourceKind: "upload",
  };
}

export function createEmptyAdminBaseDraft(): AdminBaseDraft {
  return {
    id: "new",
    status: "Активный",
    name: "",
    slug: "",
    placeTypeId: "",
    publicationStatus: "draft",
    shortDescription: "",
    attributes: {},
    region: "",
    district: "",
    city: "",
    locality: "",
    seasonality: "",
    workingHours: "{}",
    confirmedAt: "",
    publicEmail: "",
    publicPhone: "",
    publicPhoneSecondary: "",
    publicSite: "",
    telegramUrl: "",
    whatsappUrl: "",
    maxUrl: "",
    vkUrl: "",
    routeUrl: "",
    contactsSnapshot: [],
    videoLinks: "",
    amenitySlugs: [],
    coverPlaceholderConfirmed: false,
    lake: "",
    coordinates: "",
    address: "",
    ownerName: "",
    ownerPhone: "",
    managerName: "",
    managerPhone: "",
    adminPhones: ["", "", ""],
    site: "",
    accommodationType: "Апартаменты",
    apartmentCount: "0",
    beds: "0",
    bbqPrivate: "0",
    bbqShared: "0",
    baths: "0",
    poolsPrivate: "0",
    poolsShared: "0",
    saunas: "0",
    markerSize: "Стандарт",
    markerIcon: "tent",
    description: "",
    minPrice: "",
    priceMode: "none",
    currency: "RUB",
    gallery: [],
    videoUrl: "",
    videoPosterUrl: "",
    videoSourceKind: "upload",
    apartments: [createEmptyApartment(1)],
  };
}
