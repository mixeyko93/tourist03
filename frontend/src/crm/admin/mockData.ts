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
  apartments: AdminBaseApartment[];
};

export type AdminBaseRow = {
  id: string;
  status: AdminBaseStatus;
  name: string;
  lake: string;
  coordinates: string;
  owner: string;
  manager: string;
  minPrice: string;
};

export type AdminUserBooking = {
  id: string;
  base: string;
  room: string;
  dates: string;
  guests: number;
  status: "Подтверждена" | "Ожидание" | "Завершена";
  createdAt: string;
};

export type AdminUserEvent = {
  at: string;
  event: string;
  data: string;
};

export type AdminUser = {
  id: string;
  name: string;
  phone: string;
  email: string;
  createdAt: string;
  status: string;
  bookings: AdminUserBooking[];
  events: AdminUserEvent[];
};

export type AdminAccount = {
  id: string;
  login: string;
  name: string;
  baseIds: string[];
  status: "Активна" | "Отключена";
  createdAt: string;
};

export const adminBaseRows: AdminBaseRow[] = [
  {
    id: "1",
    status: "Активный",
    name: "Ангир",
    lake: "Щучье",
    coordinates: "51.40615, 106.535513",
    owner: "Жакмыксамбаев Самбула Хатурович, +7 987 087 98 78",
    manager: "Засандаль Картык Блантуевна, +7 989 989 98 65",
    minPrice: "3 500 ₽",
  },
  {
    id: "2",
    status: "Активный",
    name: "Хаяны",
    lake: "Гусиное",
    coordinates: "51.1001, 106.1000",
    owner: "Иванов Степан Баирович, +7 999 999 99 99",
    manager: "Батуев Жаргал Харитонович, +7 888 888 88 88",
    minPrice: "3 000 ₽",
  },
  {
    id: "3",
    status: "Активный",
    name: "Гостиный Дворъ",
    lake: "Байкал",
    coordinates: "53.2001, 108.3000",
    owner: "Харитонов Игорь Байгалович, +7 980 908 09 89",
    manager: "Шестерной Олег Жаргалович, +7 980 908 09 90",
    minPrice: "4 000 ₽",
  },
];

export const adminBaseDrafts: Record<string, AdminBaseDraft> = {
  "1": {
    id: "1",
    status: "Активный",
    name: "Ангир",
    lake: "Щучье",
    coordinates: "51.40615, 106.535513",
    address: "Республика Бурятия, Селенгинский район, сельское поселение Загустайское, территория Южное побережье Щучьего озера",
    ownerName: "Жакмыксамбаев Самбула Хатурович",
    ownerPhone: "+7 987 087 98 78",
    managerName: "Засандаль Картык Блантуевна",
    managerPhone: "+7 989 989 98 65",
    adminPhones: ["+7 777 77 77 77", "+7 777 77 77 34", "+7 777 77 77 23"],
    site: "https://angir.turist03.ru",
    accommodationType: "Апартаменты",
    apartmentCount: "4",
    beds: "12",
    bbqPrivate: "1",
    bbqShared: "1",
    baths: "1",
    poolsPrivate: "0",
    poolsShared: "0",
    saunas: "1",
    markerSize: "Стандарт",
    markerIcon: "waves",
    description: "Комфортная база отдыха на Щучьем озере с семейными апартаментами, сауной и двумя BBQ-зонами.",
    minPrice: "3 500 ₽",
    gallery: ["Главное фото", "Территория", "BBQ-зона"],
    apartments: [
      {
        id: "apt-1",
        unitType: "Апартамент",
        name: "Стандарт",
        guests: "2",
        singleBeds: "1",
        doubleBeds: "2",
        shower: "Душ общий",
        bbq: "Общий",
        sauna: "Общая",
        pool: "Бассейн — нет",
        conditioner: "Кондиционер — нет",
        description: "Базовый апартамент с видом на территорию и быстрым доступом к общим зонам.",
        weekdayPrice: "3500",
        weekendPrice: "2500",
        extraGuestPrice: "0",
        quantity: "10",
        bookingWindow: "3",
        photos: ["Фасад", "Интерьер", "Санузел"],
      },
      {
        id: "apt-2",
        unitType: "Апартамент",
        name: "Семейный",
        guests: "4",
        singleBeds: "2",
        doubleBeds: "1",
        shower: "Душ в номере",
        bbq: "Индивидуальный",
        sauna: "Общая",
        pool: "Бассейн — нет",
        conditioner: "Кондиционер — да",
        description: "Просторный вариант для семьи с отдельной BBQ-зоной и кухонным уголком.",
        weekdayPrice: "5200",
        weekendPrice: "6100",
        extraGuestPrice: "700",
        quantity: "4",
        bookingWindow: "7",
        photos: ["Комната", "Спальня", "Терраса"],
      },
    ],
  },
  "2": {
    id: "2",
    status: "Активный",
    name: "Хаяны",
    lake: "Гусиное",
    coordinates: "51.1001, 106.1000",
    address: "Садоводческий кооператив Уголёк, 117, сельское поселение Загустайское, Селенгинский район, Республика Бурятия",
    ownerName: "Иванов Степан Баирович",
    ownerPhone: "+7 999 999 99 99",
    managerName: "Батуев Жаргал Харитонович",
    managerPhone: "+7 888 888 88 88",
    adminPhones: ["+7 930 444 90 10", "+7 930 444 90 11", "+7 930 444 90 12"],
    site: "https://hayany.turist03.ru",
    accommodationType: "Домики",
    apartmentCount: "8",
    beds: "18",
    bbqPrivate: "2",
    bbqShared: "1",
    baths: "2",
    poolsPrivate: "0",
    poolsShared: "1",
    saunas: "1",
    markerSize: "VIP",
    markerIcon: "tent",
    description: "База у Гусиного озера с домиками повышенной вместимости и расширенной сервисной инфраструктурой.",
    minPrice: "3 000 ₽",
    gallery: ["Домики", "Пирс", "Сауна"],
    apartments: [
      {
        id: "apt-3",
        unitType: "Домик",
        name: "Комфорт",
        guests: "3",
        singleBeds: "2",
        doubleBeds: "1",
        shower: "Душ в номере",
        bbq: "Индивидуальный",
        sauna: "Общая",
        pool: "Бассейн — общий",
        conditioner: "Кондиционер — да",
        description: "Комфортный домик с верандой и доступом к общему бассейну.",
        weekdayPrice: "4800",
        weekendPrice: "5600",
        extraGuestPrice: "500",
        quantity: "6",
        bookingWindow: "5",
        photos: ["Фасад", "Гостиная", "Веранда"],
      },
    ],
  },
  "3": {
    id: "3",
    status: "Активный",
    name: "Гостиный Дворъ",
    lake: "Байкал",
    coordinates: "53.2001, 108.3000",
    address: "Прибайкальский район, побережье озера Байкал, турзона Малое море",
    ownerName: "Харитонов Игорь Байгалович",
    ownerPhone: "+7 980 908 09 89",
    managerName: "Шестерной Олег Жаргалович",
    managerPhone: "+7 980 908 09 90",
    adminPhones: ["+7 930 120 12 10", "+7 930 120 12 11", "+7 930 120 12 12"],
    site: "https://gostiny-dvor.turist03.ru",
    accommodationType: "Отель",
    apartmentCount: "12",
    beds: "28",
    bbqPrivate: "0",
    bbqShared: "2",
    baths: "1",
    poolsPrivate: "0",
    poolsShared: "1",
    saunas: "2",
    markerSize: "VIP",
    markerIcon: "house",
    description: "Флагманская база на Байкале с номерным фондом гостиничного формата и премиальными тарифами.",
    minPrice: "4 000 ₽",
    gallery: ["Главный корпус", "Набережная", "Ресторан"],
    apartments: [
      {
        id: "apt-4",
        unitType: "Номер",
        name: "Люкс",
        guests: "4",
        singleBeds: "0",
        doubleBeds: "2",
        shower: "Душ в номере",
        bbq: "Общий",
        sauna: "Общая",
        pool: "Бассейн — общий",
        conditioner: "Кондиционер — да",
        description: "Премиальный люкс с панорамным видом и расширенным сервисом.",
        weekdayPrice: "12000",
        weekendPrice: "14000",
        extraGuestPrice: "1200",
        quantity: "2",
        bookingWindow: "14",
        photos: ["Спальня", "Вид", "Гостиная"],
      },
    ],
  },
};

export const archivedBaseRows: AdminBaseRow[] = [
  {
    id: "14",
    status: "В архиве",
    name: "Лесная Гавань",
    lake: "Щучье",
    coordinates: "51.3199, 106.4822",
    owner: "Гармаев Алексей Эдуардович, +7 914 400 11 22",
    manager: "Батомункуева Ирина, +7 924 100 45 67",
    minPrice: "2 800 ₽",
  },
  {
    id: "18",
    status: "В архиве",
    name: "Сосновый Берег",
    lake: "Байкал",
    coordinates: "52.9411, 107.6570",
    owner: "Балданов Пётр Николаевич, +7 924 300 11 11",
    manager: "Николаева Мария, +7 924 300 22 22",
    minPrice: "3 900 ₽",
  },
];

export const adminUsers: AdminUser[] = [
  {
    id: "1",
    name: "Иван Петров",
    phone: "+7 900 000 00 00",
    email: "",
    createdAt: "03.01.2026, 19:41",
    status: "Телефон не подтверждён, email не указан",
    bookings: [
      {
        id: "#5311",
        base: "Ангир",
        room: "Стандарт",
        dates: "14.04.2026 — 17.04.2026",
        guests: 2,
        status: "Подтверждена",
        createdAt: "11.04.2026, 13:12",
      },
    ],
    events: [
      { at: "03.01.2026, 19:41", event: "Регистрация", data: "Создан аккаунт по номеру телефона" },
      { at: "11.04.2026, 13:12", event: "Создана бронь", data: "Ангир, Стандарт, 2 гостя" },
    ],
  },
  {
    id: "2",
    name: "Семен Семенов",
    phone: "+7 912 234 32 23",
    email: "233223@bk.ru",
    createdAt: "03.01.2026, 19:48",
    status: "Почта подтверждена",
    bookings: [
      {
        id: "#5410",
        base: "Гостиный Дворъ",
        room: "Люкс",
        dates: "21.04.2026 — 24.04.2026",
        guests: 3,
        status: "Ожидание",
        createdAt: "20.04.2026, 08:40",
      },
      {
        id: "#5205",
        base: "Хаяны",
        room: "Комфорт",
        dates: "05.03.2026 — 07.03.2026",
        guests: 2,
        status: "Завершена",
        createdAt: "28.02.2026, 21:14",
      },
    ],
    events: [
      { at: "03.01.2026, 19:48", event: "Регистрация", data: "Создан аккаунт по телефону и email" },
      { at: "20.04.2026, 08:40", event: "Новая бронь", data: "Гостиный Дворъ, Люкс" },
      { at: "20.04.2026, 08:45", event: "Оплата", data: "Предоплата 30%" },
    ],
  },
  {
    id: "3",
    name: "Лаврон Погосян",
    phone: "+7 096 396 39 69",
    email: "name@bk.co",
    createdAt: "03.01.2026, 19:55",
    status: "Почта подтверждена",
    bookings: [],
    events: [{ at: "03.01.2026, 19:55", event: "Регистрация", data: "Пользователь зарегистрирован" }],
  },
  {
    id: "4",
    name: "Николай Власов",
    phone: "+7 946 525 65 56",
    email: "",
    createdAt: "03.01.2026, 20:02",
    status: "Email не указан",
    bookings: [],
    events: [{ at: "03.01.2026, 20:02", event: "Регистрация", data: "Подтверждён только номер телефона" }],
  },
  {
    id: "5",
    name: "Иван Пахомов",
    phone: "+7 987 987 98 87",
    email: "",
    createdAt: "03.01.2026, 20:07",
    status: "Email не указан",
    bookings: [],
    events: [{ at: "03.01.2026, 20:07", event: "Регистрация", data: "Создан новый профиль" }],
  },
  {
    id: "6",
    name: "Карл Петров",
    phone: "+7 999 999 99 99",
    email: "",
    createdAt: "04.01.2026, 18:25",
    status: "Телефон не подтверждён",
    bookings: [],
    events: [{ at: "04.01.2026, 18:25", event: "Регистрация", data: "Аккаунт верифицирован не полностью" }],
  },
  {
    id: "7",
    name: "Маргарита",
    phone: "+7 983 459 10 35",
    email: "",
    createdAt: "07.01.2026, 21:47",
    status: "Email не указан",
    bookings: [],
    events: [{ at: "07.01.2026, 21:47", event: "Регистрация", data: "Аккаунт создан через Telegram" }],
  },
  {
    id: "8",
    name: "Михаил Бекбаев",
    phone: "+7 924 757 74 40",
    email: "",
    createdAt: "08.01.2026, 14:32",
    status: "Email не указан",
    bookings: [],
    events: [{ at: "08.01.2026, 14:32", event: "Регистрация", data: "Аккаунт создан через CRM" }],
  },
  {
    id: "9",
    name: "Михаил Стасенко",
    phone: "+7 914 633 51 93",
    email: "",
    createdAt: "31.03.2026, 21:24",
    status: "Email не указан",
    bookings: [],
    events: [{ at: "31.03.2026, 21:24", event: "Регистрация", data: "Новый пользователь добавлен в базу" }],
  },
];

export const adminAccounts: AdminAccount[] = [
  {
    id: "27",
    login: "crm@turist03.ru",
    name: "CRM Admin",
    baseIds: ["1", "2", "3"],
    status: "Активна",
    createdAt: "16.03.2026, 20:06",
  },
  {
    id: "2",
    login: "test@mail.ru",
    name: "Тест",
    baseIds: ["1", "3"],
    status: "Активна",
    createdAt: "17.11.2025, 21:59",
  },
];

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
    apartments: [createEmptyApartment(1)],
  };
}

export function cloneAdminBaseDraft(baseId?: string) {
  const source = (baseId && adminBaseDrafts[baseId]) || createEmptyAdminBaseDraft();
  return JSON.parse(JSON.stringify(source)) as AdminBaseDraft;
}

export function getAccountBaseNames(baseIds: string[]) {
  return baseIds
    .map((baseId) => adminBaseRows.find((base) => base.id === baseId)?.name)
    .filter((value): value is string => Boolean(value));
}
