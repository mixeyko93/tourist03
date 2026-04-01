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

export const campOptions: string[] = [];

export const roomOptions: string[] = [];

export const dashboardStats: DashboardStat[] = [
  {
    label: "Брони сегодня",
    value: "0",
    note: "Новые брони появятся после запуска продаж",
    delta: "0%",
  },
  {
    label: "Заселения сегодня",
    value: "0",
    note: "Заселения появятся после первых заказов",
    delta: "0%",
  },
  {
    label: "Свободных номеров",
    value: "0",
    note: "Добавьте номерной фонд для отображения доступности",
    delta: "0%",
  },
];

export const revenueSeries: RevenuePoint[] = [];

export const recentBookings: BookingPreview[] = [];

export const calendarRooms: CalendarRoom[] = [];

export const bookingRows: BookingRow[] = [];

export const roomCards: RoomCard[] = [];

export const guestRows: GuestRow[] = [];

export const serviceCards: ServiceCard[] = [];
