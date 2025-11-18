document.addEventListener('DOMContentLoaded', () => {
  initAdminCamps();
});

const adminState = {
  profile: null,
  camps: [],
  currentCampId: null,
  bookingsCache: [],
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
      toggleDashboardState();
      loadBookings();
      loadCalendar();
    });
  });

  bookingsFilterBtn?.addEventListener('click', () => {
    loadBookings();
  });

  loginForm?.addEventListener('submit', async (event) => {
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

  logoutBtn?.addEventListener('click', async () => {
    await fetch('/api/admin/logout', { method: 'POST' });
    adminState.profile = null;
    adminState.camps = [];
    adminState.currentCampId = null;
    adminState.bookingsCache = [];
    showLogin();
  });

  createBookingBtn?.addEventListener('click', () => {
    alert('Создание брони появится позже');
  });

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
    } catch {
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
      note?.classList.remove('hidden');
    } else {
      note?.classList.add('hidden');
    }
  };

  const loadMyCamps = async () => {
    try {
      const res = await fetch('/api/admin/my-camps');
      if (!res.ok) throw new Error();
      const data = await res.json();
      adminState.camps = Array.isArray(data) ? data : [];
      adminState.currentCampId = adminState.camps[0]?.id || null;
      populateCampSelects();
      toggleDashboardState();
    } catch {
      adminState.camps = [];
      adminState.currentCampId = null;
      populateCampSelects();
      toggleDashboardState();
    }
  };

  const loadBookings = async () => {
    const tbody = document.getElementById('crm-bookings-body');
    if (!tbody) return;
    setTableMessage(tbody, 6, 'Загрузка...');
    if (!adminState.camps.length) {
      setTableMessage(tbody, 6, 'У вас пока нет баз для управления');
      return;
    }
    const params = new URLSearchParams();
    if (adminState.currentCampId) params.set('camp_id', adminState.currentCampId);
    const from = bookingsDateFrom?.value;
    const to = bookingsDateTo?.value;
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
        setTableMessage(tbody, 6, 'Бронирований не найдено');
        updateSummary();
        return;
      }
      tbody.innerHTML = '';
      adminState.bookingsCache.forEach((booking) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${formatDate(booking.check_in)}</td>
          <td>${formatDate(booking.check_out)}</td>
          <td>${booking.guests_count ?? '—'}</td>
          <td>${booking.room_name || booking.room_id || '—'}</td>
          <td>${booking.status || '—'}</td>
          <td>${booking.source || '—'}</td>
        `;
        tbody.appendChild(tr);
      });
      updateSummary();
    } catch {
      setTableMessage(tbody, 6, 'Ошибка загрузки бронирований');
    }
  };

  const loadCalendar = async () => {
    const list = document.getElementById('crm-calendar-list');
    if (!list) return;
    list.innerHTML = '<div class="crm-note">Загрузка...</div>';
    if (!adminState.camps.length) {
      list.innerHTML = '<div class="crm-note">Нет доступных баз.</div>';
      return;
    }
    const params = new URLSearchParams();
    if (adminState.currentCampId) params.set('camp_id', adminState.currentCampId);
    try {
      const query = params.toString();
      const url = query ? `/api/admin/calendar?${query}` : '/api/admin/calendar';
      const res = await fetch(url);
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (!Array.isArray(data) || !data.length) {
        list.innerHTML = '<div class="crm-note">Бронирований пока нет.</div>';
        return;
      }
      list.innerHTML = '';
      data.forEach((item) => {
        const camp = adminState.camps.find((c) => c.id === item.camp_id);
        const el = document.createElement('div');
        el.className = 'crm-calendar-item';
        el.innerHTML = `
          <strong>${camp?.name || `База #${item.camp_id}`}</strong><br>
          Заезд: ${formatDate(item.check_in)} &nbsp;|&nbsp; Выезд: ${formatDate(item.check_out)}<br>
          Номер: ${item.room_id ?? '—'} &nbsp;|&nbsp; Статус: ${item.status || '—'}
        `;
        list.appendChild(el);
      });
    } catch {
      list.innerHTML = '<div class="crm-note">Ошибка загрузки календаря.</div>';
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
}

function setTableMessage(tbody, colspan, message) {
  tbody.innerHTML = `<tr><td colspan="${colspan}" class="crm-note">${message}</td></tr>`;
}

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString('ru-RU');
  } catch {
    return value;
  }
}
