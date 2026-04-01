import { Bath, BedDouble, ChevronDown, House, MapPinned, Plus, Sailboat, Save, Star, TentTree, Trash2, Trees, Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { PageMotion } from "../../components/PageMotion";
import { crmPath } from "../../paths";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { type AdminBaseApartment, type AdminBaseDraft, cloneAdminBaseDraft, createEmptyApartment } from "../mockData";

const markerOptions = [
  { key: "tent", label: "Кемпинг", icon: TentTree },
  { key: "house", label: "Домик", icon: House },
  { key: "trees", label: "Лес", icon: Trees },
  { key: "waves", label: "Берег", icon: Waves },
  { key: "ship", label: "Причал", icon: Sailboat },
] as const;

const accentBackgrounds = [
  "from-sky-500/25 to-blue-500/10",
  "from-emerald-500/25 to-teal-500/10",
  "from-amber-500/25 to-orange-500/10",
  "from-violet-500/25 to-fuchsia-500/10",
];

function ApartmentCard({
  apartment,
  index,
  onChange,
  onRemove,
}: {
  apartment: AdminBaseApartment;
  index: number;
  onChange: (next: AdminBaseApartment) => void;
  onRemove: () => void;
}) {
  const update = <K extends keyof AdminBaseApartment>(field: K, value: AdminBaseApartment[K]) => {
    onChange({ ...apartment, [field]: value });
  };

  return (
    <div className="rounded-3xl border border-border bg-background/65 p-5">
      <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Апартамент #{index + 1}</p>
          <h3 className="mt-1 text-lg font-semibold text-foreground">{apartment.name || "Новая карточка апартамента"}</h3>
        </div>
        <button type="button" className="admin-button gap-2 text-rose-300 hover:text-rose-200" onClick={onRemove}>
          <Trash2 className="h-4 w-4" />
          Удалить
        </button>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-8">
        <AdminField label="Тип размещения" className="xl:col-span-2">
          <div className="relative">
            <select className="admin-input appearance-none pr-10" value={apartment.unitType} onChange={(event) => update("unitType", event.target.value)}>
              {["Апартамент", "Домик", "Номер", "Шале"].map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>
        </AdminField>
        <AdminField label="Название" className="xl:col-span-2">
          <input className="admin-input" value={apartment.name} onChange={(event) => update("name", event.target.value)} />
        </AdminField>
        <AdminField label="Гостей">
          <input className="admin-input text-center" value={apartment.guests} onChange={(event) => update("guests", event.target.value)} />
        </AdminField>
        <AdminField label="Односпальных">
          <input className="admin-input text-center" value={apartment.singleBeds} onChange={(event) => update("singleBeds", event.target.value)} />
        </AdminField>
        <AdminField label="Двуспальных">
          <input className="admin-input text-center" value={apartment.doubleBeds} onChange={(event) => update("doubleBeds", event.target.value)} />
        </AdminField>
        <AdminField label="Количество">
          <input className="admin-input text-center" value={apartment.quantity} onChange={(event) => update("quantity", event.target.value)} />
        </AdminField>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        {[
          { field: "shower", label: "Душ" },
          { field: "bbq", label: "BBQ" },
          { field: "sauna", label: "Сауна" },
          { field: "pool", label: "Бассейн" },
          { field: "conditioner", label: "Кондиционер" },
        ].map((item) => (
          <AdminField key={item.field} label={item.label}>
            <div className="relative">
              <select
                className="admin-input appearance-none pr-10"
                value={apartment[item.field as keyof AdminBaseApartment] as string}
                onChange={(event) => update(item.field as keyof AdminBaseApartment, event.target.value)}
              >
                {[
                  apartment[item.field as keyof AdminBaseApartment] as string,
                  "Индивидуальный",
                  "Общий",
                  "Нет",
                  "Да",
                ]
                  .filter((option, optionIndex, all) => all.indexOf(option) === optionIndex)
                  .map((option) => (
                    <option key={option}>{option}</option>
                  ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </AdminField>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-6">
        <AdminField label="Описание" className="lg:col-span-2">
          <input className="admin-input" value={apartment.description} onChange={(event) => update("description", event.target.value)} />
        </AdminField>
        <AdminField label="Будни, ₽">
          <input className="admin-input text-center" value={apartment.weekdayPrice} onChange={(event) => update("weekdayPrice", event.target.value)} />
        </AdminField>
        <AdminField label="Выходные, ₽">
          <input className="admin-input text-center" value={apartment.weekendPrice} onChange={(event) => update("weekendPrice", event.target.value)} />
        </AdminField>
        <AdminField label="Доп. гость, ₽">
          <input className="admin-input text-center" value={apartment.extraGuestPrice} onChange={(event) => update("extraGuestPrice", event.target.value)} />
        </AdminField>
        <AdminField label="Окно бронирования, дн.">
          <input className="admin-input text-center" value={apartment.bookingWindow} onChange={(event) => update("bookingWindow", event.target.value)} />
        </AdminField>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {apartment.photos.map((photo, photoIndex) => (
          <div key={`${apartment.id}-${photo}`} className={`relative h-20 w-28 overflow-hidden rounded-2xl border border-border bg-gradient-to-br ${accentBackgrounds[photoIndex % accentBackgrounds.length]}`}>
            <div className="absolute inset-x-0 bottom-0 bg-card/85 px-2 py-1 text-[11px] font-medium text-foreground">{photo}</div>
          </div>
        ))}
        <button type="button" className="admin-button min-h-20 min-w-28 justify-center gap-2">
          <Plus className="h-4 w-4" />
          Фото
        </button>
      </div>
    </div>
  );
}

export default function AdminBaseEditPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [draft, setDraft] = useState<AdminBaseDraft>(() => cloneAdminBaseDraft(id));

  useEffect(() => {
    setDraft(cloneAdminBaseDraft(id));
  }, [id]);

  const updateField = <K extends keyof AdminBaseDraft>(field: K, value: AdminBaseDraft[K]) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const updateAdminPhone = (index: number, value: string) => {
    setDraft((current) => ({
      ...current,
      adminPhones: current.adminPhones.map((phone, phoneIndex) => (phoneIndex === index ? value : phone)),
    }));
  };

  const updateApartment = (index: number, apartment: AdminBaseApartment) => {
    setDraft((current) => ({
      ...current,
      apartments: current.apartments.map((item, itemIndex) => (itemIndex === index ? apartment : item)),
    }));
  };

  const addApartment = () => {
    setDraft((current) => ({
      ...current,
      apartments: [...current.apartments, createEmptyApartment(current.apartments.length + 1)],
    }));
  };

  const removeApartment = (index: number) => {
    setDraft((current) => ({
      ...current,
      apartments: current.apartments.length > 1 ? current.apartments.filter((_, itemIndex) => itemIndex !== index) : current.apartments,
    }));
  };

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="p-5 sm:p-6 lg:p-8">
        <div className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {draft.id === "new" ? "Новая база" : `База #${draft.id}`}
            </p>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">
              {draft.id === "new" ? "Создание базы отдыха" : `Редактирование базы «${draft.name}»`}
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Заполните контакты, параметры размещения, визуальные маркеры и описание апартаментов. Все блоки собраны в одну управляемую форму.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button type="button" className="admin-button" onClick={() => navigate(crmPath("/admin/archive"))}>
              В архив
            </button>
            <button type="button" className="admin-button text-rose-300 hover:text-rose-200">
              Удалить
            </button>
            <button type="button" className="admin-primary-button gap-2">
              <Save className="h-4 w-4" />
              Сохранить
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => updateField("status", "Активный")}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              draft.status === "Активный" ? "bg-emerald-500 text-white" : "border border-border bg-background/70 text-muted-foreground hover:bg-accent"
            }`}
          >
            Активный
          </button>
          <button
            type="button"
            onClick={() => updateField("status", "Отключен")}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              draft.status === "Отключен" ? "bg-amber-500 text-white" : "border border-border bg-background/70 text-muted-foreground hover:bg-accent"
            }`}
          >
            Отключен
          </button>
          <AdminStatusBadge tone={draft.status === "Активный" ? "success" : "warning"}>{draft.status}</AdminStatusBadge>
        </div>

        <div className="mt-8 space-y-8">
          <div className="grid gap-4 xl:grid-cols-4">
            <AdminField label="Название базы">
              <input className="admin-input" value={draft.name} onChange={(event) => updateField("name", event.target.value)} />
            </AdminField>
            <AdminField label="Озеро">
              <input className="admin-input" value={draft.lake} onChange={(event) => updateField("lake", event.target.value)} />
            </AdminField>
            <AdminField label="Координаты">
              <input className="admin-input" value={draft.coordinates} onChange={(event) => updateField("coordinates", event.target.value)} />
            </AdminField>
            <AdminField label="Минимальная цена">
              <input className="admin-input" value={draft.minPrice} onChange={(event) => updateField("minPrice", event.target.value)} />
            </AdminField>
          </div>

          <AdminField label="Адрес">
            <input className="admin-input" value={draft.address} onChange={(event) => updateField("address", event.target.value)} />
          </AdminField>

          <div className="grid gap-4 xl:grid-cols-4">
            <AdminField label="Владелец — ФИО">
              <input className="admin-input" value={draft.ownerName} onChange={(event) => updateField("ownerName", event.target.value)} />
            </AdminField>
            <AdminField label="Владелец — телефон">
              <input className="admin-input" value={draft.ownerPhone} onChange={(event) => updateField("ownerPhone", event.target.value)} />
            </AdminField>
            <AdminField label="Управляющий — ФИО">
              <input className="admin-input" value={draft.managerName} onChange={(event) => updateField("managerName", event.target.value)} />
            </AdminField>
            <AdminField label="Управляющий — телефон">
              <input className="admin-input" value={draft.managerPhone} onChange={(event) => updateField("managerPhone", event.target.value)} />
            </AdminField>
          </div>

          <div className="grid gap-4 xl:grid-cols-4">
            {draft.adminPhones.map((phone, index) => (
              <AdminField key={`phone-${index}`} label={`Телефон администратора №${index + 1}`}>
                <input className="admin-input" value={phone} onChange={(event) => updateAdminPhone(index, event.target.value)} />
              </AdminField>
            ))}
            <AdminField label="Сайт базы">
              <input className="admin-input" value={draft.site} onChange={(event) => updateField("site", event.target.value)} />
            </AdminField>
          </div>

          <div className="space-y-5 border-t border-border pt-8">
            <div className="flex flex-wrap items-center gap-3">
              <MapPinned className="h-5 w-5 text-blue-500" />
              <h3 className="text-lg font-semibold text-foreground">Параметры размещения и инфраструктуры</h3>
            </div>

            <div className="grid gap-4 xl:grid-cols-6">
              <AdminField label="Тип жилья" className="xl:col-span-2">
                <div className="relative">
                  <select
                    className="admin-input appearance-none pr-10"
                    value={draft.accommodationType}
                    onChange={(event) => updateField("accommodationType", event.target.value)}
                  >
                    {["Апартаменты", "Домики", "Отель", "Шале"].map((option) => (
                      <option key={option}>{option}</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                </div>
              </AdminField>
              <AdminField label="Количество апартаментов">
                <input className="admin-input" value={draft.apartmentCount} onChange={(event) => updateField("apartmentCount", event.target.value)} />
              </AdminField>
              <AdminField label="Спальных мест">
                <input className="admin-input" value={draft.beds} onChange={(event) => updateField("beds", event.target.value)} />
              </AdminField>
              <AdminField label="Зон BBQ индивидуальных">
                <input className="admin-input" value={draft.bbqPrivate} onChange={(event) => updateField("bbqPrivate", event.target.value)} />
              </AdminField>
              <AdminField label="Зон BBQ общих">
                <input className="admin-input" value={draft.bbqShared} onChange={(event) => updateField("bbqShared", event.target.value)} />
              </AdminField>
              <AdminField label="Бань">
                <input className="admin-input" value={draft.baths} onChange={(event) => updateField("baths", event.target.value)} />
              </AdminField>
              <AdminField label="Бассейнов индивидуальных">
                <input className="admin-input" value={draft.poolsPrivate} onChange={(event) => updateField("poolsPrivate", event.target.value)} />
              </AdminField>
              <AdminField label="Бассейнов общих">
                <input className="admin-input" value={draft.poolsShared} onChange={(event) => updateField("poolsShared", event.target.value)} />
              </AdminField>
              <AdminField label="Саун">
                <input className="admin-input" value={draft.saunas} onChange={(event) => updateField("saunas", event.target.value)} />
              </AdminField>
            </div>
          </div>

          <div className="space-y-5 border-t border-border pt-8">
            <div className="flex flex-wrap items-center gap-3">
              <Star className="h-5 w-5 text-blue-500" />
              <h3 className="text-lg font-semibold text-foreground">Фотографии и визуальный маркер</h3>
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-3xl border border-border bg-background/60 p-5">
                <div className="flex flex-wrap gap-3">
                  {draft.gallery.map((photo, photoIndex) => (
                    <div
                      key={photo}
                      className={`relative h-28 w-36 overflow-hidden rounded-2xl border border-border bg-gradient-to-br ${accentBackgrounds[photoIndex % accentBackgrounds.length]}`}
                    >
                      <div className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-card/85 px-2.5 py-1 text-[11px] font-semibold text-foreground">
                        {photoIndex === 0 ? <Star className="h-3 w-3 text-blue-500" /> : null}
                        {photo}
                      </div>
                    </div>
                  ))}
                  <button type="button" className="admin-button min-h-28 min-w-36 justify-center gap-2">
                    <Plus className="h-4 w-4" />
                    Загрузить фото
                  </button>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">До 20 фотографий. Первое фото используется как обложка в карточке базы.</p>
              </div>

              <div className="rounded-3xl border border-border bg-background/60 p-5">
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    {(["Стандарт", "VIP"] as const).map((size) => (
                      <button
                        key={size}
                        type="button"
                        onClick={() => updateField("markerSize", size)}
                        className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                          draft.markerSize === size ? "bg-blue-500 text-white" : "border border-border bg-background/70 text-muted-foreground hover:bg-accent"
                        }`}
                      >
                        {size}
                      </button>
                    ))}
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {markerOptions.map((option) => {
                      const Icon = option.icon;
                      const isSelected = draft.markerIcon === option.key;
                      return (
                        <button
                          key={option.key}
                          type="button"
                          onClick={() => updateField("markerIcon", option.key)}
                          className={`flex flex-col items-center gap-2 rounded-2xl border p-3 text-sm transition ${
                            isSelected ? "border-blue-500 bg-blue-500/10 text-foreground" : "border-border bg-background/75 text-muted-foreground hover:bg-accent"
                          }`}
                        >
                          <Icon className={`h-5 w-5 ${isSelected ? "text-blue-500" : "text-muted-foreground"}`} />
                          <span>{option.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="rounded-2xl border border-border bg-card/75 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Предпросмотр карточки</p>
                    <div className="mt-3 flex items-center justify-between rounded-2xl border border-border bg-background/80 px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{draft.name || "Новая база"}</p>
                        <p className="text-xs text-muted-foreground">{draft.lake || "Озеро не указано"}</p>
                      </div>
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-500">
                        {(() => {
                          const SelectedIcon = markerOptions.find((option) => option.key === draft.markerIcon)?.icon ?? TentTree;
                          return <SelectedIcon className="h-5 w-5" />;
                        })()}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3 border-t border-border pt-8">
            <div className="flex items-center gap-3">
              <Bath className="h-5 w-5 text-blue-500" />
              <h3 className="text-lg font-semibold text-foreground">Описание базы</h3>
            </div>
            <textarea className="admin-input min-h-28 resize-y" value={draft.description} onChange={(event) => updateField("description", event.target.value)} />
          </div>

          <div className="space-y-5 border-t border-border pt-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <BedDouble className="h-5 w-5 text-blue-500" />
                <h3 className="text-lg font-semibold text-foreground">Описание апартаментов</h3>
              </div>
              <button type="button" className="admin-primary-button gap-2" onClick={addApartment}>
                <Plus className="h-4 w-4" />
                Добавить апартамент
              </button>
            </div>

            <div className="space-y-4">
              {draft.apartments.map((apartment, index) => (
                <ApartmentCard
                  key={apartment.id}
                  apartment={apartment}
                  index={index}
                  onChange={(next) => updateApartment(index, next)}
                  onRemove={() => removeApartment(index)}
                />
              ))}
            </div>
          </div>
        </div>
      </AdminCard>
    </PageMotion>
  );
}
