function formatDateParam(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const russianHolidayDates2026 = new Set<string>([
  "2026-01-01",
  "2026-01-02",
  "2026-01-03",
  "2026-01-04",
  "2026-01-05",
  "2026-01-06",
  "2026-01-07",
  "2026-01-08",
  "2026-01-09",
  "2026-01-10",
  "2026-01-11",
  "2026-02-21",
  "2026-02-22",
  "2026-02-23",
  "2026-03-07",
  "2026-03-08",
  "2026-03-09",
  "2026-05-01",
  "2026-05-02",
  "2026-05-03",
  "2026-05-09",
  "2026-05-10",
  "2026-05-11",
  "2026-06-12",
  "2026-06-13",
  "2026-06-14",
  "2026-11-04",
  "2026-12-31",
]);

export function isRussianHoliday2026(value: Date) {
  return russianHolidayDates2026.has(formatDateParam(value));
}

export function isWeekend(value: Date) {
  const weekday = value.getDay();
  return weekday === 0 || weekday === 6;
}

export function getProductionDayTone(value: Date) {
  if (isRussianHoliday2026(value)) {
    return "holiday";
  }
  if (isWeekend(value)) {
    return "weekend";
  }
  return "workday";
}
