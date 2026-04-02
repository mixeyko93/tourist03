import { Camera, Clapperboard, Image as ImageIcon, ImagePlus, Link2, Star } from "lucide-react";
import { useRef } from "react";

type Props = {
  title: string;
  description: string;
  photos: string[];
  videoUrl: string;
  videoPosterUrl: string;
  videoSourceKind: "upload" | "external";
  uploadPhotoLabel?: string;
  photoLimitLabel?: string;
  photoUploading?: boolean;
  videoUploading?: boolean;
  posterUploading?: boolean;
  onPhotosUpload: (files: FileList | null) => void;
  onPhotoRemove?: (index: number) => void;
  onVideoUpload: (files: FileList | null) => void;
  onPosterUpload: (files: FileList | null) => void;
  onCapturePoster: (videoEl: HTMLVideoElement | null) => void;
  onVideoSourceKindChange: (next: "upload" | "external") => void;
  onVideoUrlChange: (next: string) => void;
};

export function MediaEditorSection({
  title,
  description,
  photos,
  videoUrl,
  videoPosterUrl,
  videoSourceKind,
  uploadPhotoLabel = "Загрузить фото",
  photoLimitLabel = "Первое фото станет обложкой после модерации.",
  photoUploading = false,
  videoUploading = false,
  posterUploading = false,
  onPhotosUpload,
  onPhotoRemove,
  onVideoUpload,
  onPosterUpload,
  onCapturePoster,
  onVideoSourceKindChange,
  onVideoUrlChange,
}: Props) {
  const photoInputRef = useRef<HTMLInputElement | null>(null);
  const videoInputRef = useRef<HTMLInputElement | null>(null);
  const posterInputRef = useRef<HTMLInputElement | null>(null);
  const videoPreviewRef = useRef<HTMLVideoElement | null>(null);
  const canCapturePoster = videoSourceKind === "upload" && Boolean(videoUrl);

  return (
    <section className="space-y-4 rounded-3xl border border-border bg-background/60 p-5">
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>

      <input
        ref={photoInputRef}
        type="file"
        multiple
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          onPhotosUpload(event.target.files);
          event.currentTarget.value = "";
        }}
      />
      <input
        ref={videoInputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.m4v"
        className="hidden"
        onChange={(event) => {
          onVideoUpload(event.target.files);
          event.currentTarget.value = "";
        }}
      />
      <input
        ref={posterInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          onPosterUpload(event.target.files);
          event.currentTarget.value = "";
        }}
      />

      <div className="space-y-3 rounded-3xl border border-border bg-card/45 p-4">
        <div className="flex flex-wrap gap-3">
          {photos.map((photo, index) => (
            <div key={`${photo}-${index}`} className="relative h-24 w-32 overflow-hidden rounded-2xl border border-border bg-background/70">
              <img src={photo} alt={`Фото ${index + 1}`} className="h-full w-full object-cover" />
              {index === 0 ? (
                <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-card/85 px-2 py-1 text-[11px] font-semibold text-foreground">
                  <Star className="h-3 w-3 text-[#E5D3B3]" />
                  Обложка
                </span>
              ) : null}
              {onPhotoRemove ? (
                <button
                  type="button"
                  className="absolute right-2 top-2 rounded-full bg-black/55 px-2 py-1 text-[11px] font-medium text-white transition hover:bg-black/70"
                  onClick={() => onPhotoRemove(index)}
                >
                  Убрать
                </button>
              ) : null}
            </div>
          ))}
          <button type="button" className="soft-button min-h-24 min-w-32 justify-center gap-2" onClick={() => photoInputRef.current?.click()} disabled={photoUploading}>
            <ImagePlus className="h-4 w-4" />
            {photoUploading ? "Загрузка..." : uploadPhotoLabel}
          </button>
        </div>
        <p className="text-xs leading-5 text-muted-foreground">{photoLimitLabel}</p>
      </div>

      <div className="space-y-4 rounded-3xl border border-border bg-card/45 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Видео и обложка</p>
            <p className="text-xs leading-5 text-muted-foreground">Можно загрузить файл до 100 МБ или добавить внешнюю ссылку. Обложку можно загрузить отдельно или выбрать кадр.</p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className={`rounded-2xl border px-3 py-2 text-sm font-medium transition ${videoSourceKind === "upload" ? "border-[#E5D3B3]/40 bg-[#E5D3B3]/12 text-foreground" : "border-border bg-background/70 text-muted-foreground hover:bg-accent hover:text-foreground"}`}
              onClick={() => onVideoSourceKindChange("upload")}
            >
              Файл
            </button>
            <button
              type="button"
              className={`rounded-2xl border px-3 py-2 text-sm font-medium transition ${videoSourceKind === "external" ? "border-[#E5D3B3]/40 bg-[#E5D3B3]/12 text-foreground" : "border-border bg-background/70 text-muted-foreground hover:bg-accent hover:text-foreground"}`}
              onClick={() => onVideoSourceKindChange("external")}
            >
              Ссылка
            </button>
          </div>
        </div>

        {videoSourceKind === "external" ? (
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Ссылка на видео</span>
            <div className="relative">
              <Link2 className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input className="soft-input pl-10" value={videoUrl} onChange={(event) => onVideoUrlChange(event.target.value)} placeholder="https://..." />
            </div>
          </label>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[1fr_280px]">
          <div className="rounded-3xl border border-border bg-background/70 p-4">
            {videoSourceKind === "upload" && videoUrl ? (
              <video ref={videoPreviewRef} src={videoUrl} poster={videoPosterUrl || undefined} className="max-h-72 w-full rounded-2xl bg-black object-contain" controls preload="metadata" />
            ) : videoSourceKind === "external" && videoUrl ? (
              <div className="flex min-h-48 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-background/70 px-5 py-6 text-center">
                <Clapperboard className="h-8 w-8 text-[#E5D3B3]" />
                <a href={videoUrl} target="_blank" rel="noreferrer" className="text-sm font-medium text-foreground underline underline-offset-4">
                  Открыть источник видео
                </a>
              </div>
            ) : (
              <div className="flex min-h-48 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-background/70 px-5 py-6 text-center">
                <ImageIcon className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Видео пока не добавлено.</p>
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              {videoSourceKind === "upload" ? (
                <button type="button" className="soft-button gap-2" onClick={() => videoInputRef.current?.click()} disabled={videoUploading}>
                  <Clapperboard className="h-4 w-4" />
                  {videoUploading ? "Загрузка..." : "Загрузить видео"}
                </button>
              ) : null}
              <button type="button" className="soft-button gap-2" onClick={() => posterInputRef.current?.click()} disabled={posterUploading}>
                <ImagePlus className="h-4 w-4" />
                {posterUploading ? "Загрузка..." : "Загрузить обложку"}
              </button>
              <button type="button" className="soft-button gap-2" onClick={() => onCapturePoster(videoPreviewRef.current)} disabled={!canCapturePoster || posterUploading}>
                <Camera className="h-4 w-4" />
                Выбрать кадр
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-background/70 p-4">
            <p className="text-sm font-semibold text-foreground">Обложка видео</p>
            <div className="mt-4 flex min-h-52 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-border bg-background/70">
              {videoPosterUrl ? (
                <img src={videoPosterUrl} alt="Обложка видео" className="h-full w-full object-cover" />
              ) : (
                <div className="px-6 text-center text-sm text-muted-foreground">Загрузите отдельную картинку или выберите кадр из видео.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
