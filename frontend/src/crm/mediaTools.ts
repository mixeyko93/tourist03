export type CrmMediaFormState = {
  photos: string[];
  videoUrl: string;
  videoPosterUrl: string;
  videoSourceKind: "upload" | "external";
};

export type CrmMediaItem = {
  media_type: "image" | "video";
  url: string;
  poster_url?: string | null;
  source_kind?: "upload" | "external" | null;
  moderation_status?: string | null;
  moderation_comment?: string | null;
  cover?: boolean | number | null;
  sort?: number | null;
};

export function splitMediaItems(media: CrmMediaItem[] | undefined, fallbackPhotos: string[] = []) {
  const photos = (media || [])
    .filter((item) => item.media_type === "image" && item.url)
    .sort((left, right) => Number(left.sort || 0) - Number(right.sort || 0))
    .map((item) => item.url);
  const video = (media || []).find((item) => item.media_type === "video" && item.url);
  return {
    photos: photos.length ? photos : fallbackPhotos,
    videoUrl: video?.url || "",
    videoPosterUrl: video?.poster_url || "",
    videoSourceKind: video?.source_kind === "external" ? "external" : "upload",
  } satisfies CrmMediaFormState;
}

export function buildMediaItems(
  photos: string[],
  videoUrl: string,
  videoPosterUrl: string,
  videoSourceKind: "upload" | "external",
): CrmMediaItem[] {
  const items: CrmMediaItem[] = photos.map((url, index) => ({
    media_type: "image",
    url,
    cover: index === 0,
    sort: index,
    source_kind: "upload",
  }));
  if (videoUrl.trim()) {
    items.push({
      media_type: "video",
      url: videoUrl.trim(),
      poster_url: videoPosterUrl.trim() || undefined,
      source_kind: videoSourceKind,
      cover: false,
      sort: items.length,
    });
  }
  return items;
}

export async function captureVideoPosterFile(videoEl: HTMLVideoElement | null, fileNamePrefix: string) {
  if (!videoEl) {
    throw new Error("Сначала откройте видео и выберите кадр.");
  }
  const canvas = document.createElement("canvas");
  const width = Math.max(videoEl.videoWidth || 0, 1);
  const height = Math.max(videoEl.videoHeight || 0, 1);
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Не удалось подготовить кадр для обложки.");
  }
  context.drawImage(videoEl, 0, 0, width, height);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) {
    throw new Error("Не удалось сформировать изображение обложки.");
  }
  return new File([blob], `${fileNamePrefix}-poster.png`, { type: "image/png" });
}
