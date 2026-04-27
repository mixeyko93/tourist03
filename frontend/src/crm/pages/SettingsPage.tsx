import {
  Bell,
  Building2,
  ChevronDown,
  FileSpreadsheet,
  Link2,
  MapPinHouse,
  Phone,
  Save,
  Search,
  ShieldCheck,
  Users2,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { MediaEditorSection } from "../components/MediaEditorSection";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageMotion } from "../components/PageMotion";
import { usePageLoadState } from "../components/usePageLoadState";
import { SectionHeading } from "../components/SectionHeading";
import { SensitiveChangeModal } from "../components/SensitiveChangeModal";
import { buildMediaItems, captureVideoPosterFile, splitMediaItems } from "../mediaTools";
import {
  createCrmChangeRequest,
  createCrmStaff,
  fetchCrmAuditLog,
  fetchCrmCampProfile,
  fetchCrmCamps,
  fetchCrmStaff,
  issueCrmStaffTelegramLink,
  saveCrmCampProfile,
  uploadCrmMedia,
  updateCrmStaff,
  type CrmAuditEntry,
  type CrmCamp,
  type CrmCampProfileUpdatePayload,
  type CrmStaffMember,
  type CrmStaffPermissionMeta,
  type CrmStaffRoleMeta,
  type CrmStaffUpsertPayload,
} from "../session";

type ProfileForm = {
  name: string;
  lakeName: string;
  address: string;
  phone: string;
  siteUrl: string;
  description: string;
  timeZone: string;
  checkInTime: string;
  checkOutTime: string;
  cancellationPolicy: string;
  arrivalInstructions: string;
  paymentInstructions: string;
  adminContactPhone: string;
  supportWhatsapp: string;
  supportTelegram: string;
  notificationsEnabled: boolean;
  photos: string[];
  videoUrl: string;
  videoPosterUrl: string;
  videoSourceKind: "upload" | "external";
};

type StaffForm = {
  login: string;
  displayName: string;
  phone: string;
  password: string;
  roleKey: string;
  canManageStaff: boolean;
  isPrimary: boolean;
  isActive: boolean;
  notificationsEnabled: boolean;
  permissionKeys: string[];
};

type SettingsTab = "profile" | "team" | "audit";

type TelegramLinkInfo = {
  code: string;
  bot_username: string;
};

const emptyProfileForm: ProfileForm = {
  name: "",
  lakeName: "",
  address: "",
  phone: "",
  siteUrl: "",
  description: "",
  timeZone: "Asia/Irkutsk",
  checkInTime: "",
  checkOutTime: "",
  cancellationPolicy: "",
  arrivalInstructions: "",
  paymentInstructions: "",
  adminContactPhone: "",
  supportWhatsapp: "",
  supportTelegram: "",
  notificationsEnabled: true,
  photos: [],
  videoUrl: "",
  videoPosterUrl: "",
  videoSourceKind: "upload",
};

const defaultRolePermissions: Record<string, string[]> = {
  chief_manager: [
    "manage_staff_accounts",
    "manage_staff_permissions",
    "manage_shift_schedule",
    "manage_camp_visibility",
    "manage_pricing",
    "manage_cancellation_policy",
    "manage_rooms",
    "manage_services",
    "manage_templates",
    "manage_notifications",
    "manage_bookings",
    "manage_payments",
    "view_audit_log",
    "export_data",
  ],
  administrator: [
    "manage_staff_accounts",
    "manage_staff_permissions",
    "manage_shift_schedule",
    "manage_camp_visibility",
    "manage_pricing",
    "manage_cancellation_policy",
    "manage_rooms",
    "manage_services",
    "manage_templates",
    "manage_notifications",
    "manage_bookings",
    "manage_payments",
    "view_audit_log",
    "export_data",
  ],
  booking_manager: ["manage_bookings", "manage_payments", "manage_notifications", "view_audit_log", "export_data"],
  content_manager: ["manage_rooms", "manage_services", "manage_templates", "manage_camp_visibility", "view_audit_log"],
  finance_manager: ["manage_payments", "view_audit_log", "export_data"],
  viewer: ["view_audit_log"],
};

const tabOptions: Array<{ key: SettingsTab; label: string }> = [
  { key: "profile", label: "Профиль базы" },
  { key: "team", label: "Команда" },
  { key: "audit", label: "Журнал действий" },
];

function mapProfileForm(payload: Awaited<ReturnType<typeof fetchCrmCampProfile>>): ProfileForm {
  const media = splitMediaItems(payload.media, payload.photos.map((photo) => photo.url));
  return {
    name: payload.camp.name || "",
    lakeName: payload.camp.lake_name || "",
    address: payload.camp.address || "",
    phone: payload.camp.phone || "",
    siteUrl: payload.camp.site_url || "",
    description: payload.camp.description || "",
    timeZone: payload.settings.time_zone || "Asia/Irkutsk",
    checkInTime: payload.settings.check_in_time || "",
    checkOutTime: payload.settings.check_out_time || "",
    cancellationPolicy: payload.settings.cancellation_policy || "",
    arrivalInstructions: payload.settings.arrival_instructions || "",
    paymentInstructions: payload.settings.payment_instructions || "",
    adminContactPhone: payload.settings.admin_contact_phone || "",
    supportWhatsapp: payload.settings.support_whatsapp || "",
    supportTelegram: payload.settings.support_telegram || "",
    notificationsEnabled: payload.settings.notifications_enabled ?? true,
    photos: media.photos,
    videoUrl: media.videoUrl,
    videoPosterUrl: media.videoPosterUrl,
    videoSourceKind: media.videoSourceKind,
  };
}

function toProfilePayload(form: ProfileForm): CrmCampProfileUpdatePayload {
  return {
    name: form.name,
    lake_name: form.lakeName,
    address: form.address,
    phone: form.phone,
    site_url: form.siteUrl,
    description: form.description,
    time_zone: form.timeZone,
    check_in_time: form.checkInTime,
    check_out_time: form.checkOutTime,
    cancellation_policy: form.cancellationPolicy,
    arrival_instructions: form.arrivalInstructions,
    payment_instructions: form.paymentInstructions,
    admin_contact_phone: form.adminContactPhone,
    support_whatsapp: form.supportWhatsapp,
    support_telegram: form.supportTelegram,
    notifications_enabled: form.notificationsEnabled,
    media: buildMediaItems(form.photos, form.videoUrl, form.videoPosterUrl, form.videoSourceKind),
  };
}

function createEmptyStaffForm(roleKey = "administrator"): StaffForm {
  return {
    login: "",
    displayName: "",
    phone: "",
    password: "",
    roleKey,
    canManageStaff: roleKey === "chief_manager" || roleKey === "administrator",
    isPrimary: false,
    isActive: true,
    notificationsEnabled: true,
    permissionKeys: [...(defaultRolePermissions[roleKey] || [])],
  };
}

function mapStaffForm(staff: CrmStaffMember): StaffForm {
  return {
    login: staff.login,
    displayName: staff.display_name,
    phone: staff.phone || "",
    password: "",
    roleKey: staff.role_key || "administrator",
    canManageStaff: staff.can_manage_staff,
    isPrimary: staff.is_primary,
    isActive: staff.is_active,
    notificationsEnabled: staff.notifications_enabled,
    permissionKeys: [...staff.permission_keys],
  };
}

function toStaffPayload(form: StaffForm): CrmStaffUpsertPayload {
  return {
    login: form.login,
    display_name: form.displayName,
    phone: form.phone || undefined,
    password: form.password || undefined,
    role_key: form.roleKey,
    can_manage_staff: form.canManageStaff,
    is_primary: form.isPrimary,
    is_active: form.isActive,
    notifications_enabled: form.notificationsEnabled,
    permission_keys: form.permissionKeys,
  };
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Не указано";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function downloadCsv(filename: string, rows: Array<Record<string, string | number | boolean | null | undefined>>) {
  if (!rows.length || typeof window === "undefined") {
    return;
  }
  const headers = Object.keys(rows[0]);
  const escapeCell = (value: string | number | boolean | null | undefined) =>
    `"${String(value ?? "").replaceAll('"', '""')}"`;
  const content = [headers.join(";"), ...rows.map((row) => headers.map((header) => escapeCell(row[header])).join(";"))].join("\n");
  const blob = new Blob([`\ufeff${content}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [profileForm, setProfileForm] = useState<ProfileForm>(emptyProfileForm);
  const [loadedCancellationPolicy, setLoadedCancellationPolicy] = useState("");
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileUploadKey, setProfileUploadKey] = useState<null | "photos" | "video" | "poster">(null);
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");
  const [profilePendingApproval, setProfilePendingApproval] = useState(false);
  const [teamItems, setTeamItems] = useState<CrmStaffMember[]>([]);
  const [teamRoles, setTeamRoles] = useState<CrmStaffRoleMeta[]>([]);
  const [teamPermissions, setTeamPermissions] = useState<CrmStaffPermissionMeta[]>([]);
  const [teamSearch, setTeamSearch] = useState("");
  const [teamError, setTeamError] = useState("");
  const [teamSuccess, setTeamSuccess] = useState("");
  const [isTeamLoading, setIsTeamLoading] = useState(false);
  const [isStaffModalOpen, setIsStaffModalOpen] = useState(false);
  const [editingStaff, setEditingStaff] = useState<CrmStaffMember | null>(null);
  const [staffForm, setStaffForm] = useState<StaffForm>(createEmptyStaffForm());
  const [staffFormError, setStaffFormError] = useState("");
  const [isSavingStaff, setIsSavingStaff] = useState(false);
  const [telegramLinkInfo, setTelegramLinkInfo] = useState<TelegramLinkInfo | null>(null);
  const [issuingTelegramCodeId, setIssuingTelegramCodeId] = useState<number | null>(null);
  const [auditItems, setAuditItems] = useState<CrmAuditEntry[]>([]);
  const [auditActors, setAuditActors] = useState<Array<{ id: number; label: string }>>([]);
  const [auditTargetTypes, setAuditTargetTypes] = useState<string[]>([]);
  const [auditSearch, setAuditSearch] = useState("");
  const [auditActorId, setAuditActorId] = useState<number | null>(null);
  const [auditTargetType, setAuditTargetType] = useState("");
  const [auditError, setAuditError] = useState("");
  const [isAuditLoading, setIsAuditLoading] = useState(false);
  const [selectedAuditEntry, setSelectedAuditEntry] = useState<CrmAuditEntry | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsBootLoading(true);
    fetchCrmCamps(controller.signal)
      .then((items) => {
        setCamps(items);
        setSelectedCampId((current) => {
          if (!items.length) {
            return null;
          }
          if (current && items.some((item) => item.id === current)) {
            return current;
          }
          return items[0].id;
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setProfileError(error instanceof Error ? error.message : "Не удалось загрузить список баз");
        setCamps([]);
        setSelectedCampId(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsBootLoading(false);
        }
      });
    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setProfileForm(emptyProfileForm);
      return;
    }
    const controller = new AbortController();
    setIsProfileLoading(true);
    setProfileError("");
    setProfileSuccess("");
    fetchCrmCampProfile(selectedCampId, controller.signal)
      .then((payload) => {
        setProfileForm(mapProfileForm(payload));
        setLoadedCancellationPolicy(payload.settings.cancellation_policy || "");
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setProfileError(error instanceof Error ? error.message : "Не удалось загрузить профиль базы");
        setProfileForm(emptyProfileForm);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsProfileLoading(false);
        }
      });
    return () => controller.abort();
  }, [selectedCampId, reloadKey]);

  useEffect(() => {
    if (!selectedCampId || activeTab !== "team") {
      return;
    }
    const controller = new AbortController();
    setIsTeamLoading(true);
    setTeamError("");
    fetchCrmStaff(selectedCampId, controller.signal)
      .then((payload) => {
        setTeamItems(payload.items);
        setTeamRoles(payload.roles);
        setTeamPermissions(payload.permissions);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setTeamError(error instanceof Error ? error.message : "Не удалось загрузить команду базы");
        setTeamItems([]);
        setTeamRoles([]);
        setTeamPermissions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsTeamLoading(false);
        }
      });
    return () => controller.abort();
  }, [selectedCampId, activeTab, reloadKey]);

  useEffect(() => {
    if (!selectedCampId || activeTab !== "audit") {
      return;
    }
    const controller = new AbortController();
    setIsAuditLoading(true);
    setAuditError("");
    fetchCrmAuditLog(
      selectedCampId,
      {
        search: auditSearch || undefined,
        actorId: auditActorId,
        targetType: auditTargetType || undefined,
        limit: 250,
      },
      controller.signal,
    )
      .then((payload) => {
        setAuditItems(payload.items);
        setAuditActors(payload.actors);
        setAuditTargetTypes(payload.target_types);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setAuditError(error instanceof Error ? error.message : "Не удалось загрузить журнал действий");
        setAuditItems([]);
        setAuditActors([]);
        setAuditTargetTypes([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsAuditLoading(false);
        }
      });
    return () => controller.abort();
  }, [selectedCampId, activeTab, auditSearch, auditActorId, auditTargetType, reloadKey]);

  const filteredTeamItems = useMemo(() => {
    const query = teamSearch.trim().toLowerCase();
    if (!query) {
      return teamItems;
    }
    return teamItems.filter((staff) =>
      [staff.display_name, staff.login, staff.phone, staff.role_label].filter(Boolean).join(" ").toLowerCase().includes(query),
    );
  }, [teamItems, teamSearch]);

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setProfileError("Сначала выберите базу.");
      return;
    }
    const payload = toProfilePayload(profileForm);
    if ((profileForm.cancellationPolicy || "").trim() !== (loadedCancellationPolicy || "").trim()) {
      setProfilePendingApproval(true);
      setProfileError("");
      setProfileSuccess("");
      return;
    }
    try {
      setIsSavingProfile(true);
      setProfileError("");
      setProfileSuccess("");
      const response = await saveCrmCampProfile(selectedCampId, payload);
      setProfileForm(mapProfileForm(response.item));
      setLoadedCancellationPolicy(response.item.settings.cancellation_policy || "");
      setProfileSuccess("Профиль базы сохранён.");
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Не удалось сохранить настройки");
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function uploadProfilePhotos(files: FileList | null) {
    if (!selectedCampId || !files?.length) {
      return;
    }
    try {
      setProfileUploadKey("photos");
      setProfileError("");
      const uploaded = await Promise.all(Array.from(files).slice(0, Math.max(0, 20 - profileForm.photos.length)).map((file) => uploadCrmMedia(file, { campId: selectedCampId })));
      setProfileForm((current) => ({
        ...current,
        photos: [...current.photos, ...uploaded.map((item) => item.url)].slice(0, 20),
      }));
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Не удалось загрузить фотографии базы");
    } finally {
      setProfileUploadKey(null);
    }
  }

  async function uploadProfileVideo(files: FileList | null) {
    if (!selectedCampId || !files?.length) {
      return;
    }
    try {
      setProfileUploadKey("video");
      setProfileError("");
      const uploaded = await uploadCrmMedia(files[0], { campId: selectedCampId });
      setProfileForm((current) => ({
        ...current,
        videoUrl: uploaded.url,
        videoSourceKind: "upload",
      }));
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Не удалось загрузить видео базы");
    } finally {
      setProfileUploadKey(null);
    }
  }

  async function uploadProfilePoster(files: FileList | null) {
    if (!selectedCampId || !files?.length) {
      return;
    }
    try {
      setProfileUploadKey("poster");
      setProfileError("");
      const uploaded = await uploadCrmMedia(files[0], { campId: selectedCampId });
      setProfileForm((current) => ({
        ...current,
        videoPosterUrl: uploaded.url,
      }));
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Не удалось загрузить обложку видео");
    } finally {
      setProfileUploadKey(null);
    }
  }

  async function captureProfilePoster(videoEl: HTMLVideoElement | null) {
    if (!selectedCampId) {
      return;
    }
    try {
      setProfileUploadKey("poster");
      setProfileError("");
      const file = await captureVideoPosterFile(videoEl, `camp-${selectedCampId}`);
      const uploaded = await uploadCrmMedia(file, { campId: selectedCampId });
      setProfileForm((current) => ({
        ...current,
        videoPosterUrl: uploaded.url,
      }));
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Не удалось выбрать кадр для обложки");
    } finally {
      setProfileUploadKey(null);
    }
  }

  async function submitProfileSensitiveChange(applyMode: "pending_review" | "apply_with_responsibility", comment: string) {
    if (!selectedCampId) {
      return;
    }
    try {
      setIsSavingProfile(true);
      setProfileError("");
      setProfileSuccess("");
      await createCrmChangeRequest(selectedCampId, {
        operation: "camp_profile_update",
        payload: toProfilePayload(profileForm) as Record<string, unknown>,
        request_comment: comment || undefined,
        apply_mode: applyMode,
      });
      setProfilePendingApproval(false);
      if (applyMode === "apply_with_responsibility") {
        setLoadedCancellationPolicy(profileForm.cancellationPolicy);
        setReloadKey((value) => value + 1);
        setProfileSuccess("Изменение правил отмены применено под вашу ответственность.");
      } else {
        setProfileSuccess("Изменение правил отмены отправлено на подтверждение.");
      }
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Не удалось обработать чувствительное изменение");
    } finally {
      setIsSavingProfile(false);
    }
  }

  function openCreateStaffModal() {
    const firstRole = teamRoles[0]?.key || "administrator";
    setEditingStaff(null);
    setStaffForm(createEmptyStaffForm(firstRole));
    setStaffFormError("");
    setTeamSuccess("");
    setTelegramLinkInfo(null);
    setIsStaffModalOpen(true);
  }

  function openEditStaffModal(staff: CrmStaffMember) {
    setEditingStaff(staff);
    setStaffForm(mapStaffForm(staff));
    setStaffFormError("");
    setTelegramLinkInfo(null);
    setIsStaffModalOpen(true);
  }

  async function handleStaffSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setStaffFormError("Сначала выберите базу.");
      return;
    }
    if (!staffForm.login.trim() || !staffForm.displayName.trim()) {
      setStaffFormError("Заполните логин и имя сотрудника.");
      return;
    }
    if (!editingStaff && !staffForm.password.trim()) {
      setStaffFormError("Для новой учётки нужно задать пароль.");
      return;
    }
    try {
      setIsSavingStaff(true);
      setStaffFormError("");
      setTeamError("");
      setTeamSuccess("");
      if (editingStaff) {
        await updateCrmStaff(selectedCampId, editingStaff.id, toStaffPayload(staffForm));
        setTeamSuccess(`Учётка ${staffForm.displayName} обновлена.`);
      } else {
        await createCrmStaff(selectedCampId, toStaffPayload(staffForm));
        setTeamSuccess(`Учётка ${staffForm.displayName} создана.`);
      }
      setIsStaffModalOpen(false);
      setEditingStaff(null);
      setTelegramLinkInfo(null);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setStaffFormError(error instanceof Error ? error.message : "Не удалось сохранить учётку сотрудника");
    } finally {
      setIsSavingStaff(false);
    }
  }

  async function handleIssueTelegramCode(staff: CrmStaffMember) {
    if (!selectedCampId) {
      return;
    }
    try {
      setIssuingTelegramCodeId(staff.id);
      setStaffFormError("");
      setTeamError("");
      if (!isStaffModalOpen) {
        openEditStaffModal(staff);
      }
      const response = await issueCrmStaffTelegramLink(selectedCampId, staff.id);
      setTelegramLinkInfo({
        code: response.code,
        bot_username: response.bot_username,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось выпустить код привязки Telegram";
      setTeamError(message);
      setStaffFormError(message);
    } finally {
      setIssuingTelegramCodeId(null);
    }
  }

  const hasCampOptions = camps.length > 0;
  const { isPageVisible } = usePageLoadState(isBootLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <SectionHeading
        title="Профиль, команда и контроль"
        description="Живой центр управления базой: данные объекта, команда сотрудников, роли, Telegram-привязки и журнал действий."
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,280px)_auto] lg:items-center lg:justify-between">
          <div className="relative">
            <select
              className="soft-input appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60"
              value={selectedCampId ?? ""}
              onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
              disabled={!hasCampOptions || isBootLoading}
            >
              {hasCampOptions ? (
                camps.map((camp) => (
                  <option key={camp.id} value={camp.id}>
                    {camp.name}
                  </option>
                ))
              ) : (
                <option value="">Нет доступных баз</option>
              )}
            </select>
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>

          <div className="flex flex-wrap gap-2">
            {tabOptions.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`rounded-2xl border px-4 py-2.5 text-sm font-medium transition ${
                  activeTab === tab.key
                    ? "border-[#E5D3B3]/30 bg-[#E5D3B3]/10 text-foreground"
                    : "border-border bg-background/65 text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
            <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)}>
              Обновить данные
            </button>
          </div>
        </div>
      </section>

      {!hasCampOptions && !isBootLoading ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Building2}
            title="Нет доступных баз"
            description="Когда вам выдадут доступ к базе, её профиль, сотрудники и журнал действий появятся здесь."
          />
        </section>
      ) : null}

      {activeTab === "profile" && hasCampOptions ? (
        <>
          {isProfileLoading ? (
            <section className="glass-card p-6">
              <PageLoadingState blocks={3} columnsClassName="grid-cols-1" blockHeightClassName="h-56" />
            </section>
          ) : (
            <form onSubmit={handleProfileSubmit} className="space-y-6">
              {profileError ? (
                <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
                  {profileError}
                </section>
              ) : null}

              {profileSuccess ? (
                <section className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-sm text-emerald-200">
                  {profileSuccess}
                </section>
              ) : null}

              <section className="glass-card p-6 md:p-8">
                <div className="flex items-center gap-3">
                  <Building2 className="h-5 w-5 text-[#E5D3B3]" />
                  <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Основная информация</h2>
                </div>

                <div className="mt-6 grid gap-5 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Название базы отдыха</span>
                    <input className="soft-input" value={profileForm.name} onChange={(event) => setProfileForm((current) => ({ ...current, name: event.target.value }))} required />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Озеро / локация</span>
                    <input className="soft-input" value={profileForm.lakeName} onChange={(event) => setProfileForm((current) => ({ ...current, lakeName: event.target.value }))} placeholder="Например: Щучье" />
                  </label>
                  <label className="space-y-2 md:col-span-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Адрес</span>
                    <input className="soft-input" value={profileForm.address} onChange={(event) => setProfileForm((current) => ({ ...current, address: event.target.value }))} />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Контактный телефон базы</span>
                    <input className="soft-input" value={profileForm.phone} onChange={(event) => setProfileForm((current) => ({ ...current, phone: event.target.value }))} />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Сайт базы</span>
                    <input className="soft-input" value={profileForm.siteUrl} onChange={(event) => setProfileForm((current) => ({ ...current, siteUrl: event.target.value }))} placeholder="https://..." />
                  </label>
                  <label className="space-y-2 md:col-span-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Описание</span>
                    <textarea className="soft-input min-h-32 resize-none" value={profileForm.description} onChange={(event) => setProfileForm((current) => ({ ...current, description: event.target.value }))} />
                  </label>
                </div>
              </section>

              <section className="glass-card p-6 md:p-8">
                <div className="flex items-center gap-3">
                  <MapPinHouse className="h-5 w-5 text-[#E5D3B3]" />
                  <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Правила проживания</h2>
                </div>

                <div className="mt-6 grid gap-5 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Часовой пояс</span>
                    <input className="soft-input" value={profileForm.timeZone} onChange={(event) => setProfileForm((current) => ({ ...current, timeZone: event.target.value }))} />
                  </label>
                  <div className="grid gap-5 sm:grid-cols-2">
                    <label className="space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заезд</span>
                      <input type="time" className="soft-input" value={profileForm.checkInTime} onChange={(event) => setProfileForm((current) => ({ ...current, checkInTime: event.target.value }))} />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Выезд</span>
                      <input type="time" className="soft-input" value={profileForm.checkOutTime} onChange={(event) => setProfileForm((current) => ({ ...current, checkOutTime: event.target.value }))} />
                    </label>
                  </div>
                  <label className="space-y-2 md:col-span-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Правила отмены</span>
                    <textarea className="soft-input min-h-28 resize-none" value={profileForm.cancellationPolicy} onChange={(event) => setProfileForm((current) => ({ ...current, cancellationPolicy: event.target.value }))} />
                  </label>
                  <label className="space-y-2 md:col-span-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Инструкция перед заездом</span>
                    <textarea className="soft-input min-h-28 resize-none" value={profileForm.arrivalInstructions} onChange={(event) => setProfileForm((current) => ({ ...current, arrivalInstructions: event.target.value }))} />
                  </label>
                  <label className="space-y-2 md:col-span-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Инструкция по оплате</span>
                    <textarea className="soft-input min-h-28 resize-none" value={profileForm.paymentInstructions} onChange={(event) => setProfileForm((current) => ({ ...current, paymentInstructions: event.target.value }))} />
                  </label>
                </div>
              </section>

              <section className="glass-card p-6 md:p-8">
                <div className="flex items-center gap-3">
                  <Phone className="h-5 w-5 text-[#E5D3B3]" />
                  <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Контакты и уведомления</h2>
                </div>

                <div className="mt-6 grid gap-5 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Телефон администратора</span>
                    <input className="soft-input" value={profileForm.adminContactPhone} onChange={(event) => setProfileForm((current) => ({ ...current, adminContactPhone: event.target.value }))} />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">WhatsApp поддержки</span>
                    <input className="soft-input" value={profileForm.supportWhatsapp} onChange={(event) => setProfileForm((current) => ({ ...current, supportWhatsapp: event.target.value }))} />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Telegram поддержки</span>
                    <input className="soft-input" value={profileForm.supportTelegram} onChange={(event) => setProfileForm((current) => ({ ...current, supportTelegram: event.target.value }))} />
                  </label>
                  <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/65 px-4 py-3 md:self-end">
                    <input type="checkbox" className="h-4 w-4 rounded border-border bg-background" checked={profileForm.notificationsEnabled} onChange={(event) => setProfileForm((current) => ({ ...current, notificationsEnabled: event.target.checked }))} />
                    <div>
                      <p className="text-sm font-medium text-foreground">Уведомления базы включены</p>
                      <p className="text-xs text-muted-foreground">Отключение сохранится в CRM и будет видно в аудите.</p>
                    </div>
                  </label>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-3">
                  <div className="rounded-3xl border border-border bg-background/65 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <Bell className="h-4 w-4 text-[#E5D3B3]" />
                      Уведомления
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">Базовый переключатель уже связан с серверными настройками базы.</p>
                  </div>
                  <div className="rounded-3xl border border-border bg-background/65 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <Link2 className="h-4 w-4 text-[#E5D3B3]" />
                      Контакты
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">Эти контакты используются в клиентских уведомлениях и в разделе помощи.</p>
                  </div>
                  <div className="rounded-3xl border border-border bg-background/65 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <ShieldCheck className="h-4 w-4 text-[#E5D3B3]" />
                      Аудит
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">Все сохранения профиля уже попадают в журнал действий CRM.</p>
                  </div>
                </div>
              </section>

              <MediaEditorSection
                title="Фото и видео базы"
                description="Загружайте изображения, видео и обложки прямо из CRM. Новый публичный контент попадёт в очередь модерации суперадмина."
                photos={profileForm.photos}
                videoUrl={profileForm.videoUrl}
                videoPosterUrl={profileForm.videoPosterUrl}
                videoSourceKind={profileForm.videoSourceKind}
                uploadPhotoLabel="Добавить фото базы"
                photoLimitLabel="До 20 фотографий. Первое фото станет обложкой базы после модерации."
                photoUploading={profileUploadKey === "photos"}
                videoUploading={profileUploadKey === "video"}
                posterUploading={profileUploadKey === "poster"}
                onPhotosUpload={uploadProfilePhotos}
                onPhotoRemove={(index) =>
                  setProfileForm((current) => ({
                    ...current,
                    photos: current.photos.filter((_, photoIndex) => photoIndex !== index),
                  }))
                }
                onVideoUpload={uploadProfileVideo}
                onPosterUpload={uploadProfilePoster}
                onCapturePoster={captureProfilePoster}
                onVideoSourceKindChange={(next) => setProfileForm((current) => ({ ...current, videoSourceKind: next }))}
                onVideoUrlChange={(next) => setProfileForm((current) => ({ ...current, videoUrl: next }))}
              />

              <div className="flex flex-col gap-3 sm:flex-row">
                <button type="submit" className="brand-button gap-2 disabled:cursor-not-allowed disabled:opacity-60" disabled={isSavingProfile}>
                  <Save className="h-4 w-4" />
                  {isSavingProfile ? "Сохраняем профиль..." : "Сохранить изменения"}
                </button>
                <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)} disabled={isSavingProfile}>
                  Сбросить к серверной версии
                </button>
              </div>
            </form>
          )}
        </>
      ) : null}

      {activeTab === "team" && hasCampOptions ? (
        <div className="space-y-6">
          <section className="glass-card p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="relative w-full lg:max-w-md">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  className="soft-input pl-11"
                  placeholder="Поиск по имени, логину, телефону или роли"
                  value={teamSearch}
                  onChange={(event) => setTeamSearch(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)}>
                  Обновить команду
                </button>
                <button type="button" className="brand-button gap-2" onClick={openCreateStaffModal}>
                  <Users2 className="h-4 w-4" />
                  Добавить сотрудника
                </button>
              </div>
            </div>
          </section>

          {teamError ? (
            <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
              {teamError}
            </section>
          ) : null}

          {teamSuccess ? (
            <section className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-sm text-emerald-200">
              {teamSuccess}
            </section>
          ) : null}

          {isTeamLoading ? (
            <section className="glass-card p-6">
              <PageLoadingState blocks={2} columnsClassName="xl:grid-cols-2" blockHeightClassName="h-56" />
            </section>
          ) : filteredTeamItems.length ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {filteredTeamItems.map((staff) => (
                <article key={staff.id} className="glass-card p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h2 className="truncate text-lg font-semibold tracking-[-0.03em] text-foreground">{staff.display_name}</h2>
                      <p className="mt-1 truncate text-sm text-muted-foreground">{staff.login}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="rounded-full border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 px-3 py-1 text-xs font-medium text-[#E5D3B3]">
                          {staff.role_label}
                        </span>
                        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${staff.is_active ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-rose-500/25 bg-rose-500/10 text-rose-300"}`}>
                          {staff.is_active ? "Активен" : "Отключён"}
                        </span>
                        {staff.can_manage_staff ? (
                          <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-300">
                            Управляет командой
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 sm:min-w-[150px]">
                      <button type="button" className="soft-button" onClick={() => openEditStaffModal(staff)}>
                        Редактировать
                      </button>
                      <button
                        type="button"
                        className="rounded-2xl border border-border bg-background/70 px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-accent"
                        onClick={() => handleIssueTelegramCode(staff)}
                        disabled={issuingTelegramCodeId === staff.id}
                      >
                        {issuingTelegramCodeId === staff.id ? "Генерируем..." : staff.has_telegram_link ? "Перепривязать Telegram" : "Привязать Telegram"}
                      </button>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-3 md:grid-cols-2">
                    <div className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Телефон</p>
                      <p className="mt-2 text-sm font-medium text-foreground">{staff.phone || "Не указан"}</p>
                    </div>
                    <div className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Telegram</p>
                      <p className="mt-2 text-sm font-medium text-foreground">{staff.has_telegram_link ? `Подключён ${staff.telegram_username ? `(${staff.telegram_username})` : ""}` : "Не подключён"}</p>
                    </div>
                    <div className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Последний вход</p>
                      <p className="mt-2 text-sm font-medium text-foreground">{formatDateTime(staff.last_seen_at)}</p>
                    </div>
                    <div className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Уведомления</p>
                      <p className="mt-2 text-sm font-medium text-foreground">{staff.notifications_enabled ? "Включены" : "Отключены"}</p>
                    </div>
                  </div>

                  <div className="mt-5">
                    <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Права в этой базе</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {staff.permission_keys.length ? (
                        staff.permission_keys.map((permissionKey) => {
                          const label = teamPermissions.find((permission) => permission.key === permissionKey)?.label || permissionKey;
                          return (
                            <span key={permissionKey} className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                              {label}
                            </span>
                          );
                        })
                      ) : (
                        <span className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-muted-foreground">
                          Отдельные права не назначены
                        </span>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <section className="glass-card p-6">
              <EmptyState
                icon={Users2}
                title="Команда пока не настроена"
                description="Создайте сотрудников базы, задайте роли, права и выпустите код привязки Telegram для оперативных уведомлений."
              />
            </section>
          )}
        </div>
      ) : null}

      {activeTab === "audit" && hasCampOptions ? (
        <div className="space-y-6">
          <section className="glass-card p-5">
            <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_220px_220px_auto_auto] xl:items-center">
              <div className="relative">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  className="soft-input pl-11"
                  placeholder="Поиск по сотруднику, действию, комментарию или объекту"
                  value={auditSearch}
                  onChange={(event) => setAuditSearch(event.target.value)}
                />
              </div>
              <select className="soft-input" value={auditActorId ?? ""} onChange={(event) => setAuditActorId(event.target.value ? Number(event.target.value) : null)}>
                <option value="">Все сотрудники</option>
                {auditActors.map((actor) => (
                  <option key={actor.id} value={actor.id}>
                    {actor.label}
                  </option>
                ))}
              </select>
              <select className="soft-input" value={auditTargetType} onChange={(event) => setAuditTargetType(event.target.value)}>
                <option value="">Все объекты</option>
                {auditTargetTypes.map((targetType) => (
                  <option key={targetType} value={targetType}>
                    {targetType}
                  </option>
                ))}
              </select>
              <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)}>
                Обновить журнал
              </button>
              <button
                type="button"
                className="brand-button gap-2"
                onClick={() =>
                  downloadCsv(
                    "crm-audit-log.csv",
                    auditItems.map((item) => ({
                      Дата: formatDateTime(item.created_at),
                      Сотрудник: item.actor_display || item.actor_id || "",
                      Действие: item.action_label,
                      Объект: item.target_type,
                      Идентификатор: item.target_id || "",
                      Комментарий: item.comment || "",
                      Чувствительное: item.is_sensitive ? "Да" : "Нет",
                      Автоприменение: item.was_auto_applied ? "Да" : "Нет",
                    })),
                  )
                }
                disabled={!auditItems.length}
              >
                <FileSpreadsheet className="h-4 w-4" />
                CSV
              </button>
            </div>
          </section>

          {auditError ? (
            <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
              {auditError}
            </section>
          ) : null}

          {isAuditLoading ? (
            <section className="glass-card p-6">
              <PageLoadingState blocks={1} columnsClassName="grid-cols-1" blockHeightClassName="h-[22rem]" />
            </section>
          ) : auditItems.length ? (
            <div className="space-y-3">
              {auditItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="glass-card w-full p-5 text-left transition hover:border-[#E5D3B3]/30 hover:bg-card/95"
                  onClick={() => setSelectedAuditEntry(item)}
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        <span className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                          {item.actor_display || `Сотрудник #${item.actor_id ?? "?"}`}
                        </span>
                        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${item.is_sensitive ? "border-rose-500/25 bg-rose-500/10 text-rose-300" : "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"}`}>
                          {item.is_sensitive ? "Чувствительное" : "Обычное"}
                        </span>
                        {item.was_auto_applied ? (
                          <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-300">
                            Применено сразу
                          </span>
                        ) : null}
                      </div>
                      <h2 className="text-lg font-semibold tracking-[-0.03em] text-foreground">{item.action_label}</h2>
                      <p className="text-sm text-muted-foreground">
                        Объект: {item.target_type}
                        {item.target_id ? ` #${item.target_id}` : ""}
                      </p>
                      {item.comment ? <p className="line-clamp-2 text-sm text-foreground/90">{item.comment}</p> : null}
                    </div>
                    <p className="shrink-0 text-sm text-muted-foreground">{formatDateTime(item.created_at)}</p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <section className="glass-card p-6">
              <EmptyState icon={ShieldCheck} title="Журнал действий пока пуст" description="Когда сотрудники начнут вносить изменения, здесь появится хронология всех операций по базе." />
            </section>
          )}
        </div>
      ) : null}

      <ModalShell
        open={isStaffModalOpen}
        onClose={() => {
          setIsStaffModalOpen(false);
          setEditingStaff(null);
          setStaffFormError("");
          setTelegramLinkInfo(null);
        }}
        title={editingStaff ? "Редактирование сотрудника" : "Новая учётка сотрудника"}
        description="Задайте роль, права и параметры уведомлений для команды базы. Все изменения попадут в аудит."
      >
        <form className="space-y-5" onSubmit={handleStaffSubmit}>
          {staffFormError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{staffFormError}</div>
          ) : null}

          {telegramLinkInfo ? (
            <div className="flex flex-col gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Привязка Telegram</p>
              <div className="rounded-xl bg-black/20 px-4 py-4 text-center">
                <p className="font-mono text-4xl font-bold tracking-[0.2em] text-emerald-100">{telegramLinkInfo.code}</p>
                <p className="mt-1 text-xs text-emerald-200/60">Код действителен 15 минут</p>
              </div>
              <p className="text-xs leading-5 text-emerald-200/80">
                Откройте бот{telegramLinkInfo.bot_username ? ` @${telegramLinkInfo.bot_username}` : ""} в Telegram и отправьте этот код. Бот привяжет аккаунт автоматически.
              </p>
              {telegramLinkInfo.bot_username ? (
                <a
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-300/30 bg-black/20 px-3 py-2.5 text-sm font-medium text-emerald-50 transition hover:bg-black/30"
                  href={`https://t.me/${telegramLinkInfo.bot_username}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Link2 className="h-4 w-4" />
                  Открыть бот
                </a>
              ) : null}
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Логин</span>
              <input className="soft-input" value={staffForm.login} onChange={(event) => setStaffForm((current) => ({ ...current, login: event.target.value }))} placeholder="mikhail.stasenko" required />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Имя сотрудника</span>
              <input className="soft-input" value={staffForm.displayName} onChange={(event) => setStaffForm((current) => ({ ...current, displayName: event.target.value }))} required />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Телефон</span>
              <input className="soft-input" value={staffForm.phone} onChange={(event) => setStaffForm((current) => ({ ...current, phone: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                {editingStaff ? "Новый пароль" : "Пароль"}
              </span>
              <input
                type="password"
                className="soft-input"
                value={staffForm.password}
                onChange={(event) => setStaffForm((current) => ({ ...current, password: event.target.value }))}
                placeholder={editingStaff ? "Оставьте пустым, если не нужно менять" : ""}
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Роль</span>
              <select
                className="soft-input"
                value={staffForm.roleKey}
                onChange={(event) => {
                  const nextRole = event.target.value;
                  setStaffForm((current) => ({
                    ...current,
                    roleKey: nextRole,
                    canManageStaff: nextRole === "chief_manager" || nextRole === "administrator" ? true : current.canManageStaff,
                    permissionKeys: [...(defaultRolePermissions[nextRole] || [])],
                  }));
                }}
              >
                {teamRoles.map((role) => (
                  <option key={role.key} value={role.key}>
                    {role.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/65 px-4 py-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border bg-background"
                  checked={staffForm.canManageStaff}
                  onChange={(event) => setStaffForm((current) => ({ ...current, canManageStaff: event.target.checked }))}
                />
                <span className="text-sm text-foreground">Управляет сотрудниками</span>
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/65 px-4 py-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border bg-background"
                  checked={staffForm.isPrimary}
                  onChange={(event) => setStaffForm((current) => ({ ...current, isPrimary: event.target.checked }))}
                />
                <span className="text-sm text-foreground">Главный в базе</span>
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/65 px-4 py-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border bg-background"
                  checked={staffForm.isActive}
                  onChange={(event) => setStaffForm((current) => ({ ...current, isActive: event.target.checked }))}
                />
                <span className="text-sm text-foreground">Учётка активна</span>
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/65 px-4 py-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border bg-background"
                  checked={staffForm.notificationsEnabled}
                  onChange={(event) => setStaffForm((current) => ({ ...current, notificationsEnabled: event.target.checked }))}
                />
                <span className="text-sm text-foreground">Уведомления включены</span>
              </label>
            </div>
          </div>

          <div className="space-y-3 rounded-3xl border border-border bg-background/65 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">Права в рамках базы</p>
                <p className="text-sm text-muted-foreground">Можно быстро заполнить права ролью и затем точечно поправить чекбоксы.</p>
              </div>
              <button
                type="button"
                className="soft-button"
                onClick={() => setStaffForm((current) => ({ ...current, permissionKeys: [...(defaultRolePermissions[current.roleKey] || [])] }))}
              >
                Заполнить по роли
              </button>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {teamPermissions.map((permission) => {
                const checked = staffForm.permissionKeys.includes(permission.key);
                return (
                  <label key={permission.key} className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 px-4 py-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border bg-background"
                      checked={checked}
                      onChange={(event) =>
                        setStaffForm((current) => ({
                          ...current,
                          permissionKeys: event.target.checked
                            ? [...current.permissionKeys, permission.key]
                            : current.permissionKeys.filter((item) => item !== permission.key),
                        }))
                      }
                    />
                    <span className="text-sm text-foreground">{permission.label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {editingStaff ? (
            <div className="rounded-3xl border border-border bg-background/65 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Привязка к боту уведомлений</p>
                  <p className="text-sm text-muted-foreground">Сгенерируйте одноразовый код, чтобы сотрудник подключил Telegram к своей учётке.</p>
                </div>
                <button
                  type="button"
                  className="soft-button"
                  onClick={() => editingStaff && handleIssueTelegramCode(editingStaff)}
                  disabled={issuingTelegramCodeId === editingStaff.id}
                >
                  {issuingTelegramCodeId === editingStaff.id ? "Генерируем..." : "Выдать код"}
                </button>
              </div>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              className="soft-button"
              onClick={() => {
                setIsStaffModalOpen(false);
                setEditingStaff(null);
                setStaffFormError("");
                setTelegramLinkInfo(null);
              }}
            >
              Отмена
            </button>
            <button type="submit" className="brand-button justify-center gap-2" disabled={isSavingStaff}>
              <Save className="h-4 w-4" />
              {isSavingStaff ? "Сохраняем..." : editingStaff ? "Сохранить сотрудника" : "Создать учётку"}
            </button>
          </div>
        </form>
      </ModalShell>

      <ModalShell
        open={Boolean(selectedAuditEntry)}
        onClose={() => setSelectedAuditEntry(null)}
        title={selectedAuditEntry?.action_label || "Детали действия"}
        description="Полная запись из журнала действий по выбранной базе."
      >
        {selectedAuditEntry ? (
          <div className="space-y-5">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Сотрудник</p>
                <p className="mt-2 text-sm font-medium text-foreground">{selectedAuditEntry.actor_display || `#${selectedAuditEntry.actor_id ?? "?"}`}</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Дата</p>
                <p className="mt-2 text-sm font-medium text-foreground">{formatDateTime(selectedAuditEntry.created_at)}</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Объект</p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {selectedAuditEntry.target_type}
                  {selectedAuditEntry.target_id ? ` #${selectedAuditEntry.target_id}` : ""}
                </p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Режим</p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {selectedAuditEntry.is_sensitive ? "Чувствительное изменение" : "Обычное действие"}
                  {selectedAuditEntry.was_auto_applied ? " / применено сразу" : ""}
                </p>
              </div>
            </div>

            {selectedAuditEntry.comment ? (
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Комментарий</p>
                <p className="mt-2 text-sm text-foreground">{selectedAuditEntry.comment}</p>
              </div>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Было</p>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-muted-foreground">
                  {JSON.stringify(selectedAuditEntry.old_value ?? {}, null, 2)}
                </pre>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Стало</p>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-muted-foreground">
                  {JSON.stringify(selectedAuditEntry.new_value ?? {}, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        ) : null}
      </ModalShell>

      <SensitiveChangeModal
        open={profilePendingApproval}
        title="Согласование правил отмены"
        description="Правила отмены влияют на клиента, оплату и шаблоны уведомлений. Изменение можно отправить управляющему на подтверждение или применить сразу под вашу ответственность."
        loading={isSavingProfile}
        onClose={() => {
          if (!isSavingProfile) {
            setProfilePendingApproval(false);
          }
        }}
        onConfirm={(comment) => submitProfileSensitiveChange("pending_review", comment)}
        onApply={(comment) => submitProfileSensitiveChange("apply_with_responsibility", comment)}
      />
    </PageMotion>
  );
}
