export type DashboardStat = {
  label: string;
  value: string;
  note: string;
  delta: string;
};

export type RevenuePoint = {
  month: string;
  revenue: number;
  occupancy: number;
};

export type BookingPreview = {
  id: string;
  guest: string;
  room: string;
  dates: string;
  amount: string;
  status: "confirmed" | "processing" | "completed";
};

export type CalendarBooking = {
  start: number;
  span: number;
  label: string;
  status: "processing" | "confirmed" | "cancelled" | "completed";
};

export type CalendarRoom = {
  id: string;
  title: string;
  category: string;
  bookings: CalendarBooking[];
};

export type BookingRow = {
  id: string;
  checkIn: string;
  checkOut: string;
  guests: number;
  room: string;
  status: "confirmed" | "processing" | "completed";
  payment: string;
  source: string;
};

export type RoomCard = {
  id: string;
  name: string;
  price: string;
  capacity: string;
  beds: string;
  count: number;
  active: boolean;
  features: string[];
};

export type GuestRow = {
  id: string;
  name: string;
  phone: string;
  email: string;
  visits: number;
  totalSpent: string;
  lastVisit: string;
  status: "Новый" | "Постоянный" | "VIP";
};

export type ServiceCard = {
  id: string;
  name: string;
  category: string;
  price: string;
  active: boolean;
  tone: "amber" | "sky" | "green" | "violet";
};

export const dashboardStats: DashboardStat[] = [
  {
    label: "Брони сегодня",
    value: "18",
    note: "6 новых заявок в ожидании",
    delta: "+12%",
  },
  {
    label: "Заселения сегодня",
    value: "9",
    note: "3 ранних заезда подтверждены",
    delta: "+4%",
  },
  {
    label: "Свободных номеров",
    value: "27",
    note: "Люкс почти распродан на выходные",
    delta: "-8%",
  },
];

export const revenueSeries: RevenuePoint[] = [
  { month: "Янв", revenue: 420, occupancy: 54 },
  { month: "Фев", revenue: 510, occupancy: 61 },
  { month: "Мар", revenue: 650, occupancy: 74 },
  { month: "Апр", revenue: 720, occupancy: 79 },
  { month: "Май", revenue: 810, occupancy: 83 },
  { month: "Июн", revenue: 930, occupancy: 91 },
];

export const recentBookings: BookingPreview[] = [
  {
    id: "#4012",
    guest: "Мария Соколова",
    room: "Люкс с террасой",
    dates: "03.04 — 07.04",
    amount: "48 000 ₽",
    status: "confirmed",
  },
  {
    id: "#4013",
    guest: "Семья Петровых",
    room: "Комфорт Family",
    dates: "04.04 — 10.04",
    amount: "72 500 ₽",
    status: "processing",
  },
  {
    id: "#4014",
    guest: "Никита Савельев",
    room: "Стандарт Lake View",
    dates: "05.04 — 06.04",
    amount: "8 900 ₽",
    status: "completed",
  },
];

export const calendarRooms: CalendarRoom[] = [
  {
    id: "r-101",
    title: "Стандарт 101",
    category: "Стандарт",
    bookings: [
      { start: 2, span: 3, label: "Карл П.", status: "confirmed" },
      { start: 12, span: 2, label: "Иванова", status: "processing" },
    ],
  },
  {
    id: "r-102",
    title: "Комфорт 204",
    category: "Комфорт",
    bookings: [{ start: 7, span: 4, label: "Семья Р.", status: "confirmed" }],
  },
  {
    id: "r-103",
    title: "Люкс 301",
    category: "Люкс",
    bookings: [{ start: 18, span: 5, label: "VIP гость", status: "completed" }],
  },
  {
    id: "r-104",
    title: "Family 402",
    category: "Семейный",
    bookings: [{ start: 24, span: 3, label: "Кузнецовы", status: "cancelled" }],
  },
];

export const bookingRows: BookingRow[] = [
  {
    id: "#5301",
    checkIn: "02.04.2026",
    checkOut: "04.04.2026",
    guests: 1,
    room: "Комфорт",
    status: "confirmed",
    payment: "Не оплачено • ожидание",
    source: "WebApp",
  },
  {
    id: "#5302",
    checkIn: "04.04.2026",
    checkOut: "09.04.2026",
    guests: 3,
    room: "Стандарт Family",
    status: "processing",
    payment: "Предоплата 30%",
    source: "CRM",
  },
  {
    id: "#5303",
    checkIn: "06.04.2026",
    checkOut: "08.04.2026",
    guests: 2,
    room: "Люкс с террасой",
    status: "completed",
    payment: "Оплачено полностью",
    source: "Telegram",
  },
];

export const roomCards: RoomCard[] = [
  {
    id: "std-01",
    name: "Стандарт Lake View",
    price: "3 500 ₽",
    capacity: "2 гостя",
    beds: "1 двуспальная кровать",
    count: 10,
    active: true,
    features: ["Wi-Fi", "Душ", "Кондиционер"],
  },
  {
    id: "com-01",
    name: "Комфорт Family",
    price: "5 000 ₽",
    capacity: "3 гостя",
    beds: "1 двуспальная, 1 односпальная",
    count: 5,
    active: true,
    features: ["ТВ", "Мини-бар", "Сейф", "Балкон"],
  },
  {
    id: "lux-01",
    name: "Люкс с панорамой",
    price: "12 000 ₽",
    capacity: "4 гостя",
    beds: "1 King-size, 1 диван-кровать",
    count: 2,
    active: false,
    features: ["Терраса", "Кухня", "Джакузи", "Камин"],
  },
];

export const guestRows: GuestRow[] = [
  {
    id: "g-001",
    name: "Иван Иванов",
    phone: "+7 (999) 123-45-67",
    email: "ivanov@mail.ru",
    visits: 3,
    totalSpent: "45 000 ₽",
    lastVisit: "15.01.2026",
    status: "Постоянный",
  },
  {
    id: "g-002",
    name: "Анна Смирнова",
    phone: "+7 (900) 000-11-22",
    email: "anna.s@gmail.com",
    visits: 1,
    totalSpent: "12 000 ₽",
    lastVisit: "01.03.2026",
    status: "Новый",
  },
  {
    id: "g-003",
    name: "Петр Васильев",
    phone: "+7 (911) 222-33-44",
    email: "p.vasiliev@yandex.ru",
    visits: 5,
    totalSpent: "120 000 ₽",
    lastVisit: "10.02.2026",
    status: "VIP",
  },
];

export const serviceCards: ServiceCard[] = [
  {
    id: "s-01",
    name: "Завтрак",
    category: "Питание",
    price: "500 ₽ / чел",
    active: true,
    tone: "amber",
  },
  {
    id: "s-02",
    name: "Трансфер",
    category: "Транспорт",
    price: "1 500 ₽",
    active: true,
    tone: "sky",
  },
  {
    id: "s-03",
    name: "Страховка",
    category: "Документы",
    price: "300 ₽ / день",
    active: false,
    tone: "green",
  },
  {
    id: "s-04",
    name: "Высокоскоростной Wi-Fi",
    category: "Связь",
    price: "Бесплатно",
    active: true,
    tone: "violet",
  },
];
