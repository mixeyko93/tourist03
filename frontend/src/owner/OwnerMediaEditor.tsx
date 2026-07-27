import { useState } from "react";

import { ownerApi, type OwnerChange } from "./api";

type OwnerMediaEditorProps = {
  change: OwnerChange;
  publishedMedia: Array<Record<string, unknown>>;
  onChange: (change: OwnerChange) => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
};

function replaceFailedImage(event: React.SyntheticEvent<HTMLImageElement>) {
  event.currentTarget.onerror = null;
  event.currentTarget.src = "/static/brand/turistika-icon.svg";
  event.currentTarget.classList.add("owner-media-placeholder");
}

export default function OwnerMediaEditor({
  change,
  publishedMedia,
  onChange,
  onMessage,
  onError,
}: OwnerMediaEditorProps) {
  const [busy, setBusy] = useState(false);

  async function refresh(message: string) {
    const response = await ownerApi.getChange(change.id);
    onChange(response.change);
    onMessage(message);
  }

  async function uploadPhoto(file?: File) {
    if (!file) return;
    const body = new FormData();
    body.set("file", file);
    body.set("scope", "place");
    body.set("sort_order", String(change.staged_media?.length || 0));
    body.set("is_cover", String(!change.staged_media?.length));
    setBusy(true);
    try {
      await ownerApi.uploadMedia(change.id, body);
      await refresh("Фотография добавлена в предложенные изменения");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось загрузить фотографию");
    } finally {
      setBusy(false);
    }
  }

  async function removePublishedPhoto(mediaId: number) {
    setBusy(true);
    try {
      await ownerApi.removePublishedMedia(change.id, mediaId);
      await refresh("Удаление фотографии добавлено в предложенные изменения");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось изменить галерею");
    } finally {
      setBusy(false);
    }
  }

  async function removeStagedPhoto(mediaId: number) {
    setBusy(true);
    try {
      await ownerApi.deleteStagedMedia(change.id, mediaId);
      await refresh("Новая фотография удалена из черновика");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось изменить галерею");
    } finally {
      setBusy(false);
    }
  }

  return (
    <fieldset className="owner-editor-section">
      <legend>Фото и видео</legend>
      <div className="owner-media-strip">
        {publishedMedia.map((media) => {
          const marked = change.staged_media?.some((item) => item.action === "remove" && item.target_media_id === Number(media.id));
          return (
            <div key={String(media.id)} className={marked ? "marked" : ""}>
              <img
                src={String(media.url)}
                alt=""
                width="100"
                height="74"
                sizes="100px"
                loading="lazy"
                decoding="async"
                onError={replaceFailedImage}
              />
              <button type="button" disabled={busy || marked} onClick={() => void removePublishedPhoto(Number(media.id))}>
                {marked ? "Удалится" : "Убрать"}
              </button>
            </div>
          );
        })}
        {change.staged_media?.filter((media) => media.action !== "remove" && media.public_preview_url).map((media) => (
          <div key={`staged-${media.id}`}>
            <img
              src={`${media.public_preview_url}?thumbnail=1`}
              alt="Новое фото"
              width="100"
              height="74"
              sizes="100px"
              loading="lazy"
              decoding="async"
              onError={replaceFailedImage}
            />
            <button type="button" disabled={busy} onClick={() => void removeStagedPhoto(media.id)}>Отменить</button>
          </div>
        ))}
      </div>
      <label className="owner-upload">Добавить фотографию<input disabled={busy} type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void uploadPhoto(event.target.files?.[0])} /></label>
    </fieldset>
  );
}
