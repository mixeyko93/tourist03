document.addEventListener('DOMContentLoaded', () => {
  initAdminCamps();
});

const adminState = {
  profile: null,
  camps: [],
  currentCampId: null,
  bookingsCache: [],
  calendar: {
    year: null,
    month: null, // 0-11
    roomId: null,
    mode: 'month', // 'month' | 'week'
    anchorDate: null, // Date
  },
  roomsCacheByCamp: new Map(),
};

function initAdminCamps() {
  const loginView = document.getElementById('crm-login-view');
  const appView = document.getElementById('crm-app-view');
  const loginForm = document.getElementById('crm-login-form');
  const loginError = document.getElementById('crm-login-error');
  const logoutBtn = document.getElementById('crm-logout-btn');
  const adminNameEl = document.getElementById('crm-admin-name');
  const navButtons = document.querySelectorAll('.crm-nav-btn');
  const panels = document.querySelectorAll('.crm-panel');
  const campSelects = document.querySelectorAll('.crm-camp-select');
  const bookingsFilterBtn = document.getElementById('crm-bookings-filter');
  const bookingsDateFrom = document.getElementById('crm-bookings-from');
  const bookingsDateTo = document.getElementById('crm-bookings-to');
  const createBookingBtn = document.getElementById('crm-create-booking-btn');
  const calPrevBtn = document.getElementById('crm-cal-prev');
  const calNextBtn = document.getElementById('crm-cal-next');
  const calTodayBtn = document.getElementById('crm-cal-today');
  const calTitleEl = document.getElementById('crm-cal-title');
  const calRoomSelect = document.getElementById('crm-calendar-room-select');
  const calModeMonthBtn = document.getElementById('crm-cal-mode-month');
  const calModeWeekBtn = document.getElementById('crm-cal-mode-week');
  const calGrid = document.getElementById('crm-cal-grid');

  const showLogin = () => {
    loginView.classList.remove('hidden');
    appView.classList.add('hidden');
    loginError.textContent = '';
  };

  const showApp = () => {
    loginView.classList.add('hidden');
    appView.classList.remove('hidden');
  };

  const setActivePanel = (panel) => {
    navButtons.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.crmTarget === panel);
    });
    panels.forEach((el) => {
      el.classList.toggle('active', el.dataset.crmPanel === panel);
    });
  };

  navButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.crmTarget;
      if (target) {
        setActivePanel(target);
        if (target === 'calendar') {
          loadCalendar();
        } else if (target === 'bookings') {
          loadBookings();
        }
      }
    });
  });

  campSelects.forEach((select) => {
    select.addEventListener('change', (event) => {
      adminState.currentCampId = parseInt(event.target.value || '', 10) || null;
      adminState.calendar.roomId = null;
      // keep all selectors in sync
      campSelects.forEach((s) => {
        if (!adminState.currentCampId) return;
        const v = String(adminState.currentCampId);
        if (s.value !== v) s.value = v;
      });
      toggleDashboardState();
      loadBookings();
      loadCalendar();
    });
  });

  if (calRoomSelect) {
    calRoomSelect.addEventListener('change', (event) => {
      const val = (event.target.value || '').toString();
      adminState.calendar.roomId = val ? parseInt(val, 10) || null : null;
      loadCalendar();
    });
  }

  const shiftCalendarMonth = (delta) => {
    const now = new Date();
    if (adminState.calendar.year == null || adminState.calendar.month == null) {
      adminState.calendar.year = now.getFullYear();
      adminState.calendar.month = now.getMonth();
    }
    const d = new Date(adminState.calendar.year, adminState.calendar.month + delta, 1);
    adminState.calendar.year = d.getFullYear();
    adminState.calendar.month = d.getMonth();
  };

  const shiftCalendarWeek = (deltaWeeks) => {
    const now = new Date();
    if (!adminState.calendar.anchorDate) adminState.calendar.anchorDate = now;
    const d = new Date(adminState.calendar.anchorDate);
    d.setDate(d.getDate() + deltaWeeks * 7);
    adminState.calendar.anchorDate = d;
  };

  const shiftCalendar = (delta) => {
    if (adminState.calendar.mode === 'week') shiftCalendarWeek(delta);
    else shiftCalendarMonth(delta);
    loadCalendar();
  };

  if (calPrevBtn) calPrevBtn.addEventListener('click', () => shiftCalendar(-1));
  if (calNextBtn) calNextBtn.addEventListener('click', () => shiftCalendar(1));
  if (calTodayBtn) calTodayBtn.addEventListener('click', () => {
    const now = new Date();
    adminState.calendar.anchorDate = now;
    adminState.calendar.year = now.getFullYear();
    adminState.calendar.month = now.getMonth();
    loadCalendar();
  });

  const setCalendarMode = (mode) => {
    adminState.calendar.mode = mode;
    if (calModeMonthBtn) calModeMonthBtn.style.opacity = (mode === 'month' ? '1' : '0.7');
    if (calModeWeekBtn) calModeWeekBtn.style.opacity = (mode === 'week' ? '1' : '0.7');
    loadCalendar();
  };
  if (calModeMonthBtn) calModeMonthBtn.addEventListener('click', () => setCalendarMode('month'));
  if (calModeWeekBtn) calModeWeekBtn.addEventListener('click', () => setCalendarMode('week'));

  if (calGrid) {
    calGrid.addEventListener('click', (ev) => {
      const cell = ev.target.closest('.crm-cal-cell.slot');
      if (!cell) return;
      const roomId = parseInt(cell.dataset.roomId || '', 10) || null;
      const dayIso = (cell.dataset.dayIso || '').trim();
      if (!roomId || !dayIso) return;
      openCreateBookingModal({ roomId, checkIn: dayIso });
    });
  }

  if (bookingsFilterBtn) {
    bookingsFilterBtn.addEventListener('click', () => {
      loadBookings();
    });
  }

  if (loginForm) loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    loginError.textContent = '';
    const formData = new FormData(loginForm);
    const payload = {
      email: (formData.get('email') || '').toString(),
      password: (formData.get('password') || '').toString(),
    };
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Ошибка входа');
      }
      await refreshSession();
    } catch (err) {
      loginError.textContent = err.message || 'Ошибка входа';
    }
  });

  if (logoutBtn) logoutBtn.addEventListener('click', async () => {
    await fetch('/api/admin/logout', { method: 'POST' });
    adminState.profile = null;
    adminState.camps = [];
    adminState.currentCampId = null;
    adminState.bookingsCache = [];
    showLogin();
  });

  if (createBookingBtn) {
    createBookingBtn.addEventListener('click', () => {
      openCreateBookingModal();
    });
  }

  const refreshSession = async () => {
    try {
      const res = await fetch('/api/admin/me');
      if (!res.ok) throw new Error('401');
      const data = await res.json();
      adminState.profile = data;
      adminNameEl.textContent = data.display_name;
      showApp();
      await loadMyCamps();
      setActivePanel('dashboard');
      await loadBookings();
      await loadCalendar();
    } catch (e) {
      showLogin();
    }
  };

  const populateCampSelects = () => {
    campSelects.forEach((select) => {
      select.innerHTML = '';
      if (!adminState.camps.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Нет доступных баз';
        select.appendChild(option);
        select.disabled = true;
      } else {
        select.disabled = false;
        adminState.camps.forEach((camp) => {
          const option = document.createElement('option');
          option.value = camp.id;
          option.textContent = camp.name || `База #${camp.id}`;
          select.appendChild(option);
        });
        if (adminState.currentCampId) {
          select.value = adminState.currentCampId;
        } else if (select.options.length) {
          select.selectedIndex = 0;
        }
      }
    });
  };

  const toggleDashboardState = () => {
    const note = document.getElementById('crm-dashboard-note');
    if (!adminState.camps.length) {
      if (note) note.classList.remove('hidden');
    } else {
      if (note) note.classList.add('hidden');
    }
  };

  const loadMyCamps = async () => {
    try {
      const res = await fetch('/api/admin/my-camps');
      if (!res.ok) throw new Error();
      const data = await res.json();
      adminState.camps = Array.isArray(data) ? data : [];
      adminState.currentCampId = (adminState.camps[0] && adminState.camps[0].id) ? adminState.camps[0].id : null;
      populateCampSelects();
      toggleDashboardState();
    } catch (e) {
      adminState.camps = [];
      adminState.currentCampId = null;
      populateCampSelects();
      toggleDashboardState();
    }
  };

  const loadBookings = async () => {
    const tbody = document.getElementById('crm-bookings-body');
    if (!tbody) return;
    setTableMessage(tbody, 8, 'Загрузка...');
    if (!adminState.camps.length) {
      setTableMessage(tbody, 8, 'У вас пока нет баз для управления');
      return;
    }
    const params = new URLSearchParams();
    if (adminState.currentCampId) params.set('camp_id', adminState.currentCampId);
    const from = bookingsDateFrom ? bookingsDateFrom.value : '';
    const to = bookingsDateTo ? bookingsDateTo.value : '';
    if (from) params.set('date_from', from);
    if (to) params.set('date_to', to);
    try {
      const query = params.toString();
      const url = query ? `/api/admin/bookings?${query}` : '/api/admin/bookings';
      const res = await fetch(url);
      if (!res.ok) throw new Error();
      const data = await res.json();
      adminState.bookingsCache = Array.isArray(data) ? data : [];
      if (!adminState.bookingsCache.length) {
        setTableMessage(tbody, 8, 'Бронирований не найдено');
        updateSummary();
        return;
      }
      tbody.innerHTML = '';
      adminState.bookingsCache.forEach((booking) => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.title = 'Нажмите, чтобы открыть';
        tr.innerHTML = `
          <td>${formatDate(booking.check_in)}</td>
          <td>${formatDate(booking.check_out)}</td>
          <td>${(booking.guests_count != null ? booking.guests_count : '—')}</td>
          <td>${booking.room_name || booking.room_id || '—'}</td>
          <td>${booking.status || '—'}</td>
          <td>${formatPaymentCell(booking)}</td>
          <td>${booking.source || '—'}</td>
          <td><button class="crm-logout-btn" type="button">⋯</button></td>
        `;
        tr.addEventListener('click', () => openBookingModal(booking));
        tbody.appendChild(tr);
      });
      updateSummary();
    } catch (e) {
      setTableMessage(tbody, 8, 'Ошибка загрузки бронирований');
    }
  };

	  const loadCalendar = async () => {
	    const grid = document.getElementById('crm-cal-grid');
	    const note = document.getElementById('crm-cal-note');
	    if (!grid || !note) return;
	    note.textContent = '';
	    grid.innerHTML = '';
	    if (!adminState.camps.length) {
	      note.textContent = 'Нет доступных баз.';
	      return;
	    }
	    try {
	      const campId = adminState.currentCampId;
	      if (!campId) {
	        note.textContent = 'Выберите базу отдыха для календаря.';
	        return;
	      }

	      // Rooms for filter + rows
	      const rooms = await fetchRoomsForCamp(campId);
	      populateCalendarRoomSelect(rooms);
	      const roomFilter = adminState.calendar.roomId;
	      if (!rooms.length) {
	        note.textContent = 'В этой базе пока нет номеров (апартаментов).';
	        grid.innerHTML = '';
	        return;
	      }

	      const now = new Date();
	      if (!adminState.calendar.anchorDate) adminState.calendar.anchorDate = now;
	      if (adminState.calendar.year == null || adminState.calendar.month == null) {
	        adminState.calendar.year = now.getFullYear();
	        adminState.calendar.month = now.getMonth();
	      }

	      const strip = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
	      const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
	      const startOfWeekMonday = (d) => {
	        const x = strip(d);
	        const dow = (x.getDay() + 6) % 7; // Mon=0 ... Sun=6
	        x.setDate(x.getDate() - dow);
	        return x;
	      };

	      let periodStart;
	      let periodEnd;
	      let days = [];
	      if (adminState.calendar.mode === 'week') {
	        const ws = startOfWeekMonday(adminState.calendar.anchorDate);
	        periodStart = ws;
	        periodEnd = addDays(ws, 7);
	        for (let i = 0; i < 7; i++) days.push(addDays(ws, i));
	        if (calTitleEl) {
	          const we = addDays(periodEnd, -1);
	          const left = ws.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
	          const right = we.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
	          calTitleEl.textContent = `Неделя ${left} — ${right}`;
	        }
	      } else {
	        const ms = new Date(adminState.calendar.year, adminState.calendar.month, 1);
	        const ne = new Date(adminState.calendar.year, adminState.calendar.month + 1, 1);
	        periodStart = strip(ms);
	        periodEnd = strip(ne);
	        const daysInMonth = new Date(adminState.calendar.year, adminState.calendar.month + 1, 0).getDate();
	        for (let i = 0; i < daysInMonth; i++) days.push(new Date(adminState.calendar.year, adminState.calendar.month, i + 1));
	        if (calTitleEl) {
	          const title = ms.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
	          calTitleEl.textContent = title.charAt(0).toUpperCase() + title.slice(1);
	        }
	      }

	      // visual state for mode buttons (in case of reload/first render)
	      const mode = adminState.calendar.mode;
	      const monthBtn = document.getElementById('crm-cal-mode-month');
	      const weekBtn = document.getElementById('crm-cal-mode-week');
	      if (monthBtn) monthBtn.style.opacity = (mode === 'month' ? '1' : '0.7');
	      if (weekBtn) weekBtn.style.opacity = (mode === 'week' ? '1' : '0.7');

	      const dateFrom = toIsoDateLocal(periodStart);
	      const dateTo = toIsoDateLocal(periodEnd);

	      const params = new URLSearchParams();
	      params.set('camp_id', String(campId));
	      params.set('date_from', dateFrom);
	      params.set('date_to', dateTo);
	      const res = await fetch(`/api/admin/bookings/calendar?${params.toString()}`);
	      if (!res.ok) throw new Error();
	      const data = await res.json();
	      const bookings = Array.isArray(data) ? data : [];

	      const todayIso = toIsoDateLocal(now);

	      renderCalendarGrid({
	        grid,
	        rooms,
	        bookings,
	        roomFilter,
	        days,
	        periodStart,
	        periodEnd,
	        todayIso,
	      });

	      if (!bookings.length) {
	        note.textContent = adminState.calendar.mode === 'week'
	          ? 'В этой неделе бронирований нет.'
	          : 'В этом месяце бронирований нет.';
	      }
	    } catch (e) {
	      note.textContent = 'Ошибка загрузки календаря.';
	    }
	  };

  const updateSummary = () => {
    const bookingsTodayEl = document.getElementById('crm-stat-bookings');
    const arrivalsEl = document.getElementById('crm-stat-arrivals');
    const freeRoomsEl = document.getElementById('crm-stat-free');
    const today = new Date().toISOString().slice(0, 10);
    const bookingsToday = adminState.bookingsCache.filter((b) => b.check_in === today);
    const arrivalsToday = adminState.bookingsCache.filter((b) => b.check_in === today);
    bookingsTodayEl.textContent = bookingsToday.length.toString();
    arrivalsEl.textContent = arrivalsToday.length.toString();
    freeRoomsEl.textContent = adminState.camps.length ? '—' : '0';
  };

  refreshSession();

  // allow modals to refresh both panels after updates
  adminState.reloadBookings = async () => {
    await loadBookings();
    await loadCalendar();
  };
}

async function fetchRoomsForCamp(campId) {
  if (!campId) return [];
  const cached = adminState.roomsCacheByCamp.get(campId);
  if (Array.isArray(cached)) return cached;
  try {
    const res = await fetch(`/api/rooms?camp_id=${campId}`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    const rooms = Array.isArray(data)
      ? data.map((r) => ({ id: r.id, name: r.name || `Номер #${r.id}` })).filter((r) => r.id)
      : [];
    adminState.roomsCacheByCamp.set(campId, rooms);
    return rooms;
  } catch (e) {
    adminState.roomsCacheByCamp.set(campId, []);
    return [];
  }
}

function populateCalendarRoomSelect(rooms) {
  const select = document.getElementById('crm-calendar-room-select');
  if (!select) return;
  const prev = adminState.calendar.roomId;
  select.innerHTML = '';
  const all = document.createElement('option');
  all.value = '';
  all.textContent = 'Все номера';
  select.appendChild(all);
  (rooms || []).forEach((r) => {
    const opt = document.createElement('option');
    opt.value = String(r.id);
    opt.textContent = r.name;
    select.appendChild(opt);
  });
  if (prev) select.value = String(prev);
}

function renderCalendarGrid({ grid, rooms, bookings, roomFilter, days, periodStart, periodEnd, todayIso }) {
  const dayWidth = 42;
  const roomWidth = 240;
  const dayList = Array.isArray(days) ? days : [];
  const dayCount = dayList.length;
  const rows = (rooms || []).filter((r) => !roomFilter || r.id === roomFilter);
  if (!rows.length || !dayCount) return;

  const cols = [`${roomWidth}px`];
  for (let d = 0; d < dayCount; d++) cols.push(`${dayWidth}px`);
  grid.style.gridTemplateColumns = cols.join(' ');
  grid.style.gridAutoRows = '52px';

  const weekday = (d) => {
    const names = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
    return names[d] || '';
  };

  const addCell = (text, className, row, col, html = false) => {
    const cell = document.createElement('div');
    cell.className = `crm-cal-cell ${className || ''}`.trim();
    if (html) cell.innerHTML = text;
    else cell.textContent = text;
    cell.style.gridRow = String(row);
    cell.style.gridColumn = String(col);
    grid.appendChild(cell);
    return cell;
  };

  const strip = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const ps = strip(periodStart);
  const pe = strip(periodEnd);
  const msDay = 24 * 60 * 60 * 1000;
  const dayIndex = (dt) => Math.floor((strip(dt).getTime() - ps.getTime()) / msDay);

  // header
  addCell('Номер', 'header room corner', 1, 1);
  for (let i = 0; i < dayCount; i++) {
    const dt = dayList[i];
    const iso = toIsoDateLocal(dt);
    const isToday = (todayIso && iso === todayIso) ? ' today' : '';
    const monthShort = dt.toLocaleDateString('ru-RU', { month: 'short' }).replace('.', '');
    const monthHint = (dayCount === 7 || dt.getDate() === 1) ? ` • ${monthShort}` : '';
    addCell(
      `<div class="crm-cal-daylabel"><div class="d">${dt.getDate()}</div><div class="w">${weekday(dt.getDay())}${monthHint}</div></div>`,
      `header${isToday}`,
      1,
      i + 2,
      true
    );
  }

  // map bookings by room
  const byRoom = new Map();
  (bookings || []).forEach((b) => {
    const rid = b.room_id || 0;
    if (!rid) return;
    if (!byRoom.has(rid)) byRoom.set(rid, []);
    byRoom.get(rid).push(b);
  });

  // rows + slots
  rows.forEach((room, idx) => {
    const rowNum = idx + 2;
    addCell(room.name, 'room', rowNum, 1);
    for (let i = 0; i < dayCount; i++) {
      const dt = dayList[i];
      const iso = toIsoDateLocal(dt);
      const isToday = (todayIso && iso === todayIso) ? ' today' : '';
      const cell = addCell('', `slot${isToday}`.trim(), rowNum, i + 2);
      cell.dataset.roomId = String(room.id);
      cell.dataset.dayIso = iso;
    }

    const roomBookings = byRoom.get(room.id) || [];
    roomBookings.forEach((b) => {
      const cin = parseIsoDateLocal(b.check_in) || new Date(b.check_in);
      const cout = parseIsoDateLocal(b.check_out) || new Date(b.check_out);
      if (Number.isNaN(cin.getTime()) || Number.isNaN(cout.getTime())) return;
      if (!(strip(cout) > ps && strip(cin) < pe)) return;

      const start = strip(cin) < ps ? ps : strip(cin);
      const end = strip(cout) > pe ? pe : strip(cout);
      const startIdx = Math.max(0, Math.min(dayCount - 1, dayIndex(start)));
      const endIdxEx = Math.max(1, Math.min(dayCount, dayIndex(end)));
      if (endIdxEx <= startIdx) return;

      const bar = document.createElement('div');
      const st = String(b.status || 'pending').toLowerCase();
      bar.className = `crm-cal-bar ${st}`;
      const arrivalInside = (strip(cin) >= ps && strip(cin) < pe);
      const departureInside = (strip(cout) > ps && strip(cout) <= pe);
      if (arrivalInside) bar.classList.add('arrival');
      if (departureInside) bar.classList.add('departure');
      bar.style.gridRow = String(rowNum);
      bar.style.gridColumn = `${startIdx + 2} / ${endIdxEx + 2}`;

      const who =
        b.user_name ||
        b.guest_name ||
        b.user_phone ||
        b.guest_phone ||
        (b.user_id ? `Пользователь #${b.user_id}` : 'Гость');
      const pay = formatPaymentCell(b);
      bar.innerHTML = `<span>#${b.id}</span><span class="meta">${who} • ${pay}</span>`;
      bar.title = `${who}\nЗаезд: ${formatDate(b.check_in)}\nВыезд: ${formatDate(b.check_out)}\nСтатус: ${b.status}\nОплата: ${pay}`;
      bar.addEventListener('click', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        openBookingModal(b);
      });
      grid.appendChild(bar);
    });
  });
}

function setTableMessage(tbody, colspan, message) {
  tbody.innerHTML = `<tr><td colspan="${colspan}" class="crm-note">${message}</td></tr>`;
}

function parseIsoDateLocal(value) {
  const s = (value || '').toString().trim();
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  const y = parseInt(m[1], 10);
  const mo = parseInt(m[2], 10);
  const d = parseInt(m[3], 10);
  if (!y || !mo || !d) return null;
  return new Date(y, mo - 1, d);
}

function toIsoDateLocal(dateObj) {
  if (!dateObj) return '';
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, '0');
  const d = String(dateObj.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatDate(value) {
  if (!value) return '—';
  try {
    const dt = parseIsoDateLocal(value) || new Date(value);
    return dt.toLocaleDateString('ru-RU');
  } catch (e) {
    return value;
  }
}

function formatPaymentCell(booking) {
  const ps = String(booking.payment_status || 'unpaid').toLowerCase();
  const pr = Boolean(booking.payment_required);
  const label = ps === 'paid' ? 'Оплачено' : ps === 'cash' ? 'Наличные' : 'Не оплачено';
  if (ps === 'unpaid' && pr) return `${label} • ожидание`;
  return label;
}

function openBookingModal(booking) {
  const modal = document.getElementById('crm-booking-modal');
  const closeBtn = document.getElementById('crm-booking-close');
  const saveBtn = document.getElementById('crm-booking-save');
  const statusSel = document.getElementById('crm-booking-status');
  const paymentSel = document.getElementById('crm-booking-payment');
  const payreq = document.getElementById('crm-booking-payreq');
  const info = document.getElementById('crm-booking-info');
  const err = document.getElementById('crm-booking-error');
  if (!modal || !closeBtn || !saveBtn || !statusSel || !paymentSel || !payreq || !info || !err) return;

  err.textContent = '';
  const campLabel = booking.camp_name || `База #${booking.camp_id}`;
  const roomLabel = booking.room_name || booking.room_id || '—';
  const guestName = booking.guest_name || '';
  const guestPhone = booking.guest_phone || '';
  const guestEmail = booking.guest_email || '';
  const userIdLabel = (booking.user_id != null ? booking.user_id : '—');
  const userLabel = booking.user_name
    ? `${booking.user_name} (id=${userIdLabel})`
    : (booking.user_id ? `Пользователь #${booking.user_id}` : (guestName ? guestName : 'Гость'));
  const phoneLabel = booking.user_phone || guestPhone || '';
  const emailLabel = (booking.user_email || guestEmail || '').trim();
  info.innerHTML = `
    <div><strong>${campLabel}</strong> — ${roomLabel}</div>
    <div class="crm-note" style="margin:6px 0 0;">Заезд: ${formatDate(booking.check_in)} • Выезд: ${formatDate(booking.check_out)} • Гостей: ${(booking.guests_count != null ? booking.guests_count : '—')}</div>
    <div class="crm-note" style="margin:6px 0 0;">${userLabel}${phoneLabel ? ` • ${phoneLabel}` : ''}${emailLabel ? ` • ${emailLabel}` : ''}</div>
    ${booking.comment ? `<div class="crm-note" style="margin:6px 0 0;">Комментарий: ${String(booking.comment).replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>` : ''}
  `;

  statusSel.innerHTML = '';
  ['pending','confirmed','rejected','completed','cancelled_by_user','cancelled'].forEach((v) => {
    const o = document.createElement('option');
    o.value = v;
    o.textContent =
      v === 'pending' ? 'В обработке' :
      v === 'confirmed' ? 'Подтверждено' :
      v === 'rejected' ? 'Отклонено' :
      v === 'completed' ? 'Закончено' :
      v === 'cancelled_by_user' ? 'Отменено пользователем' :
      v === 'cancelled' ? 'Отменено' : v;
    statusSel.appendChild(o);
  });
  statusSel.value = booking.status || 'pending';

  paymentSel.innerHTML = '';
  ['unpaid','paid','cash'].forEach((v) => {
    const o = document.createElement('option');
    o.value = v;
    o.textContent = v === 'unpaid' ? 'Не оплачено' : v === 'paid' ? 'Оплачено' : 'Оплата наличными';
    paymentSel.appendChild(o);
  });
  paymentSel.value = String(booking.payment_status || 'unpaid').toLowerCase();
  payreq.checked = Boolean(booking.payment_required);

  const close = () => {
    modal.classList.add('hidden');
  };
  closeBtn.onclick = close;
  modal.onclick = (ev) => { if (ev.target === modal) close(); };

  saveBtn.onclick = async () => {
    err.textContent = '';
    const payload = {
      status: statusSel.value,
      payment_status: paymentSel.value,
      payment_required: payreq.checked,
    };
    try {
      const res = await fetch(`/api/admin/bookings/${booking.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Ошибка сохранения');
      }
      close();
      if (typeof adminState.reloadBookings === 'function') {
        await adminState.reloadBookings();
      }
    } catch (e) {
      err.textContent = e.message || 'Ошибка сохранения';
    }
  };

  modal.classList.remove('hidden');
}

function openCreateBookingModal(draft = {}) {
  const modal = document.getElementById('crm-create-booking-modal');
  const closeBtn = document.getElementById('crm-create-booking-close');
  const saveBtn = document.getElementById('crm-create-booking-save');
  const info = document.getElementById('crm-create-booking-info');
  const err = document.getElementById('crm-create-booking-error');
  const roomSel = document.getElementById('crm-create-room');
  const checkin = document.getElementById('crm-create-checkin');
  const checkout = document.getElementById('crm-create-checkout');
  const guests = document.getElementById('crm-create-guests');
  const statusSel = document.getElementById('crm-create-status');
  const guestName = document.getElementById('crm-create-guest-name');
  const guestPhone = document.getElementById('crm-create-guest-phone');
  const guestEmail = document.getElementById('crm-create-guest-email');
  const comment = document.getElementById('crm-create-comment');
  if (!modal || !closeBtn || !saveBtn || !info || !err || !roomSel || !checkin || !checkout || !guests || !statusSel) return;

  const campId = adminState.currentCampId;
  if (!campId) {
    alert('Сначала выберите базу отдыха');
    return;
  }

  err.textContent = '';
	  const campObj = adminState.camps.find((c) => c.id === campId);
	  const campName = (campObj && campObj.name) ? campObj.name : `База #${campId}`;
	  info.textContent = campName;

  fetchRoomsForCamp(campId).then((rooms) => {
    roomSel.innerHTML = '';
    (rooms || []).forEach((r) => {
      const opt = document.createElement('option');
      opt.value = String(r.id);
      opt.textContent = r.name;
      roomSel.appendChild(opt);
    });
	    const firstRoomId = (rooms && rooms[0] ? rooms[0].id : null);
	    const roomId = draft.roomId || adminState.calendar.roomId || firstRoomId || null;
	    if (roomId) roomSel.value = String(roomId);
	  });

  const now = new Date();
  const start = draft.checkIn ? (parseIsoDateLocal(draft.checkIn) || now) : now;
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  checkin.value = draft.checkIn || toIsoDateLocal(start);
  checkout.value = draft.checkOut || toIsoDateLocal(end);

  guests.value = String(draft.guestsCount || 2);
  if (guestName) guestName.value = draft.guestName || '';
  if (guestPhone) guestPhone.value = draft.guestPhone || '';
  if (guestEmail) guestEmail.value = draft.guestEmail || '';
  if (comment) comment.value = draft.comment || '';

  statusSel.innerHTML = '';
  ['pending','confirmed','rejected','completed','cancelled_by_user','cancelled'].forEach((v) => {
    const o = document.createElement('option');
    o.value = v;
    o.textContent =
      v === 'pending' ? 'В обработке' :
      v === 'confirmed' ? 'Подтверждено' :
      v === 'rejected' ? 'Отклонено' :
      v === 'completed' ? 'Закончено' :
      v === 'cancelled_by_user' ? 'Отменено пользователем' :
      v === 'cancelled' ? 'Отменено' : v;
    statusSel.appendChild(o);
  });
  statusSel.value = draft.status || 'pending';

  const close = () => modal.classList.add('hidden');
  closeBtn.onclick = close;
  modal.onclick = (ev) => { if (ev.target === modal) close(); };

  saveBtn.onclick = async () => {
    err.textContent = '';
    const payload = {
      camp_id: campId,
      room_id: parseInt(roomSel.value || '', 10) || null,
      check_in: checkin.value,
      check_out: checkout.value,
      guests_count: parseInt(guests.value || '1', 10) || 1,
      status: statusSel.value,
      payment_status: 'unpaid',
      payment_required: false,
      guest_name: guestName ? guestName.value.trim() : '',
      guest_phone: guestPhone ? guestPhone.value.trim() : '',
      guest_email: guestEmail ? guestEmail.value.trim() : '',
      comment: comment ? comment.value.trim() : '',
    };
    try {
      const res = await fetch('/api/admin/bookings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Ошибка создания брони');
      }
      close();
      if (typeof adminState.reloadBookings === 'function') {
        await adminState.reloadBookings();
      }
    } catch (e) {
      err.textContent = e.message || 'Ошибка создания брони';
    }
  };

  modal.classList.remove('hidden');
}
