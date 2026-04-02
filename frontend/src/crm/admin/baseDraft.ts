export type AdminBaseStatus = "Активный" | "Отключен" | "В архиве";

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
    minPrice: "0 ₽",
    gallery: [],
    videoUrl: "",
    videoPosterUrl: "",
    videoSourceKind: "upload",
    apartments: [createEmptyApartment(1)],
  };
}
