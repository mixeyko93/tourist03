import { ArrowLeft, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  ownerApi,
  type EntityCatalog,
  type EntityKindKey,
  type OwnerEntityCreatePayload,
} from "./api";
import { OwnerRouteLoading } from "./components";
import { parseOwnerCoordinates } from "./coordinates";
import SchemaAttributeFields from "./SchemaAttributeFields";

const priceModeLabels: Record<OwnerEntityCreatePayload["price_mode"], string> = {
  from: "Цена от",
  fixed: "Фиксированная цена",
  request: "Стоимость по запросу",
  free: "Бесплатно",
  none: "Не показывать цену",
};

export default function CreateEntityPage({
  onBack,
  onCreated,
}: {
  onBack: () => void;
  onCreated: (entityId: number) => void;
}) {
  const [catalog, setCatalog] = useState<EntityCatalog | null>(null);
  const [entityKind, setEntityKind] = useState<EntityKindKey | "">("");
  const [subtype, setSubtype] = useState("");
  const [name, setName] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [region, setRegion] = useState("");
  const [district, setDistrict] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [attributes, setAttributes] = useState<Record<string, unknown>>({});
  const [priceMode, setPriceMode] = useState<OwnerEntityCreatePayload["price_mode"]>("none");
  const [minPrice, setMinPrice] = useState("");
  const [currency, setCurrency] = useState("RUB");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    ownerApi.entityCatalog()
      .then((response) => {
        if (!active) return;
        setCatalog(response);
        const firstKind = response.entityKinds.find((kind) =>
          response.entityTypes.some((type) => type.entity_kind === kind.key));
        const firstType = response.entityTypes.find((type) => type.entity_kind === firstKind?.key);
        setEntityKind(firstKind?.key || "");
        setSubtype(firstType?.slug || "");
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Не удалось загрузить типы карточек");
      });
    return () => {
      active = false;
    };
  }, []);

  const availableTypes = useMemo(
    () => (catalog?.entityTypes || []).filter((type) => type.entity_kind === entityKind && type.is_active !== false),
    [catalog?.entityTypes, entityKind],
  );
  const selectedType = availableTypes.find((type) => type.slug === subtype);
  const schema = (catalog?.entitySchemas || []).find((item) =>
    item.key === selectedType?.schema_key && item.version === selectedType.schema_version);

  function selectKind(next: EntityKindKey) {
    const firstType = catalog?.entityTypes.find((type) =>
      type.entity_kind === next && type.is_active !== false);
    setEntityKind(next);
    setSubtype(firstType?.slug || "");
    setAttributes({});
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!entityKind || !selectedType) {
      setError("Выберите категорию и тип карточки");
      return;
    }
    const coordinates = parseOwnerCoordinates(lat, lng);
    if (coordinates.error) {
      setError(coordinates.error);
      return;
    }
    try {
      setIsSaving(true);
      setError("");
      const response = await ownerApi.createEntity({
        entity_kind: entityKind,
        subtype: selectedType.slug,
        name: name.trim(),
        short_description: shortDescription.trim() || null,
        region: region.trim() || null,
        district: district.trim() || null,
        city: city.trim() || null,
        address: address.trim() || null,
        lat: coordinates.lat,
        lng: coordinates.lng,
        attributes,
        min_price: ["from", "fixed"].includes(priceMode) && minPrice
          ? Number(minPrice)
          : null,
        price_mode: priceMode,
        currency,
      });
      onCreated(Number(response.entity.entity_id || response.entity.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать карточку");
    } finally {
      setIsSaving(false);
    }
  }

  if (!catalog && !error) {
    return <OwnerRouteLoading label="Загружаем конструктор карточки…" />;
  }

  return (
    <section>
      <button className="owner-back" type="button" onClick={onBack}><ArrowLeft /> К моим объектам</button>
      <div className="owner-detail-heading">
        <div>
          <p className="owner-eyebrow">Новая карточка</p>
          <h1>Добавить в каталог</h1>
          <p>Выберите подходящий тип. Карточка станет публичной только после модерации.</p>
        </div>
      </div>
      {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
      {catalog ? (
        <form className="owner-card owner-create-entity" onSubmit={submit}>
          <fieldset className="owner-create-kind">
            <legend>Что вы добавляете?</legend>
            <div>
              {catalog.entityKinds
                .filter((kind) => catalog.entityTypes.some((type) => type.entity_kind === kind.key))
                .map((kind) => (
                  <label key={kind.key} className={entityKind === kind.key ? "selected" : ""}>
                    <input
                      type="radio"
                      name="entity-kind"
                      value={kind.key}
                      checked={entityKind === kind.key}
                      onChange={() => selectKind(kind.key)}
                    />
                    <b>{kind.name}</b>
                    <span>{kind.plural_name}</span>
                  </label>
                ))}
            </div>
          </fieldset>

          <div className="owner-create-grid">
            <label>
              Тип карточки
              <select
                required
                value={subtype}
                onChange={(event) => {
                  setSubtype(event.target.value);
                  setAttributes({});
                }}
              >
                <option value="">Выберите тип</option>
                {availableTypes.map((type) => <option key={type.id} value={type.slug}>{type.name}</option>)}
              </select>
            </label>
            <label>
              Название
              <input
                required
                maxLength={240}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Например, прогулки на катере"
              />
            </label>
            <label className="wide">
              Краткое описание
              <textarea
                rows={4}
                maxLength={2000}
                value={shortDescription}
                onChange={(event) => setShortDescription(event.target.value)}
                placeholder="Коротко расскажите, что получит путешественник"
              />
            </label>
            <label>
              Как показывать стоимость
              <select
                value={priceMode}
                onChange={(event) => {
                  const mode = event.target.value as OwnerEntityCreatePayload["price_mode"];
                  setPriceMode(mode);
                  if (["request", "free", "none"].includes(mode)) setMinPrice("");
                }}
              >
                {Object.entries(priceModeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              Стоимость, ₽
              <input
                type="number"
                min="0"
                max="1000000000"
                disabled={["request", "free", "none"].includes(priceMode)}
                value={minPrice}
                onChange={(event) => setMinPrice(event.target.value)}
                placeholder={priceMode === "from" ? "От какой суммы" : "Сумма"}
              />
            </label>
            <label>
              Валюта
              <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
                <option value="RUB">Российский рубль (RUB)</option>
                <option value="USD">Доллар США (USD)</option>
                <option value="EUR">Евро (EUR)</option>
              </select>
            </label>
          </div>

          <fieldset className="owner-editor-section">
            <legend>Адрес и точка на карте</legend>
            <div className="owner-create-grid">
              <label>
                Регион
                <input maxLength={160} value={region} onChange={(event) => setRegion(event.target.value)} />
              </label>
              <label>
                Район
                <input maxLength={160} value={district} onChange={(event) => setDistrict(event.target.value)} />
              </label>
              <label>
                Город
                <input maxLength={160} value={city} onChange={(event) => setCity(event.target.value)} />
              </label>
              <label>
                Адрес
                <input maxLength={500} value={address} onChange={(event) => setAddress(event.target.value)} />
              </label>
              <label>
                Широта
                <input
                  type="text"
                  inputMode="decimal"
                  aria-invalid={Boolean(error && parseOwnerCoordinates(lat, lng).error)}
                  value={lat}
                  onChange={(event) => {
                    setLat(event.target.value);
                    setError("");
                  }}
                  placeholder="Например, 51.8336"
                />
              </label>
              <label>
                Долгота
                <input
                  type="text"
                  inputMode="decimal"
                  aria-invalid={Boolean(error && parseOwnerCoordinates(lat, lng).error)}
                  value={lng}
                  onChange={(event) => {
                    setLng(event.target.value);
                    setError("");
                  }}
                  placeholder="Например, 107.5840"
                />
              </label>
            </div>
          </fieldset>

          {schema ? (
            <fieldset className="owner-editor-section owner-create-schema">
              <legend>{schema.name}</legend>
              <p>Поля меняются автоматически в зависимости от выбранного типа карточки.</p>
              <SchemaAttributeFields schema={schema} values={attributes} onChange={setAttributes} />
            </fieldset>
          ) : null}

          <div className="owner-create-note">
            <b>Что произойдёт дальше</b>
            <p>Мы создадим скрытый черновик и изменение для модерации. Опубликованный каталог напрямую не меняется.</p>
          </div>
          <div className="owner-editor-actions">
            <button type="button" className="owner-secondary" onClick={onBack}>Отмена</button>
            <button type="submit" className="owner-primary" disabled={isSaving || !name.trim() || !selectedType}>
              <Plus /> {isSaving ? "Создаём…" : "Создать черновик"}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
}
