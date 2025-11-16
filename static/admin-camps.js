document.addEventListener('DOMContentLoaded', () => {
  initAdminCampsUI();
});

function initAdminCampsUI() {
  const navButtons = document.querySelectorAll('.crm-nav-btn');
  const views = document.querySelectorAll('.crm-view');
  const loaded = new Set();

  const showView = (viewName) => {
    navButtons.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.crmView === viewName);
    });
    views.forEach((section) => {
      section.classList.toggle('active', section.dataset.crmPanel === viewName);
    });
    if (!loaded.has(viewName)) {
      if (viewName === 'camps') {
        loadAdminCamps();
      } else if (viewName === 'bookings') {
        loadAdminBookings();
      }
      loaded.add(viewName);
    } else if (viewName === 'camps') {
      loadAdminCamps();
    } else if (viewName === 'bookings') {
      loadAdminBookings();
    }
  };

  navButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.crmView;
      if (view) {
        showView(view);
      }
    });
  });

  showView('camps');
}

function loadAdminCamps() {
  const tbody = document.querySelector('#crm-camps-table tbody');
  if (!tbody) return;
  setTableMessage(tbody, 5, 'Загрузка...');

  fetch('/api/admin/camps')
    .then((res) => {
      if (!res.ok) throw new Error('bad status');
      return res.json();
    })
    .then((data) => {
      if (!Array.isArray(data) || !data.length) {
        setTableMessage(tbody, 5, 'Данные отсутствуют');
        return;
      }
      tbody.innerHTML = '';
      data.forEach((camp) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${camp.id ?? ''}</td>
          <td>${camp.name ?? ''}</td>
          <td>${camp.region ?? ''}</td>
          <td>
            <span class="crm-pill ${camp.is_active ? 'crm-pill--green' : 'crm-pill--gray'}">
              ${camp.is_active ? 'Да' : 'Нет'}
            </span>
          </td>
          <td><button class="crm-btn-muted" data-action="open">Открыть</button></td>
        `;
        const btn = tr.querySelector('[data-action="open"]');
        if (btn) {
          btn.addEventListener('click', () => {
            alert('Раздел в разработке');
          });
        }
        tbody.appendChild(tr);
      });
    })
    .catch(() => {
      setTableMessage(tbody, 5, 'Ошибка загрузки баз');
    });
}

function loadAdminBookings() {
  const tbody = document.querySelector('#crm-bookings-table tbody');
  if (!tbody) return;
  setTableMessage(tbody, 6, 'Загрузка...');

  fetch('/api/admin/bookings')
    .then((res) => {
      if (!res.ok) throw new Error('bad status');
      return res.json();
    })
    .then((data) => {
      if (!Array.isArray(data) || !data.length) {
        setTableMessage(tbody, 6, 'Бронирований пока нет');
        return;
      }
      tbody.innerHTML = '';
      data.forEach((booking) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${booking.id ?? ''}</td>
          <td>${booking.camp_name ?? '—'}</td>
          <td>${booking.check_in ?? '—'}</td>
          <td>${booking.check_out ?? '—'}</td>
          <td>${booking.guests_count ?? '—'}</td>
          <td>${booking.status ?? '—'}</td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(() => {
      setTableMessage(tbody, 6, 'Ошибка загрузки бронирований');
    });
}

function setTableMessage(tbody, colspan, message) {
  tbody.innerHTML = `<tr><td colspan="${colspan}" class="crm-table-note">${message}</td></tr>`;
}
