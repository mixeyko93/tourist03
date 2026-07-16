(() => {
  const gallery = document.querySelector("[data-place-gallery]");
  if (!gallery) return;

  const track = gallery.querySelector("[data-gallery-track]");
  const slides = [...gallery.querySelectorAll("[data-gallery-slide]")];
  const thumbnails = [...gallery.querySelectorAll("[data-gallery-thumbnail]")];
  const counter = gallery.querySelector("[data-gallery-counter]");
  const dialog = gallery.querySelector("[data-gallery-dialog]");
  const dialogImage = gallery.querySelector("[data-gallery-dialog-image]");
  const dialogCaption = gallery.querySelector("[data-gallery-dialog-caption]");
  if (!track || slides.length < 2) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let activeIndex = 0;
  let scrollFrame = 0;

  function normalizedIndex(index) {
    return (index + slides.length) % slides.length;
  }

  function updateDialog(index) {
    if (!dialogImage) return;
    const source = slides[index].querySelector("img");
    const caption = slides[index].querySelector("figcaption")?.textContent?.trim() || "";
    dialogImage.src = source?.currentSrc || source?.src || "";
    dialogImage.alt = source?.alt || "";
    if (dialogCaption) {
      dialogCaption.textContent = caption;
      dialogCaption.hidden = !caption;
    }
  }

  function setActive(index, { scroll = true } = {}) {
    activeIndex = normalizedIndex(index);
    if (counter) counter.textContent = `${activeIndex + 1} / ${slides.length}`;
    thumbnails.forEach((thumbnail, position) => {
      if (position === activeIndex) thumbnail.setAttribute("aria-current", "true");
      else thumbnail.removeAttribute("aria-current");
    });
    if (scroll) {
      track.scrollTo({
        left: slides[activeIndex].offsetLeft,
        behavior: reducedMotion.matches ? "auto" : "smooth",
      });
    }
    updateDialog(activeIndex);
  }

  function openDialog(index) {
    setActive(index, { scroll: false });
    if (!dialog) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeDialog() {
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
    setActive(activeIndex);
  }

  gallery.querySelector("[data-gallery-previous]")?.addEventListener("click", () => setActive(activeIndex - 1));
  gallery.querySelector("[data-gallery-next]")?.addEventListener("click", () => setActive(activeIndex + 1));
  gallery.querySelector("[data-gallery-dialog-previous]")?.addEventListener("click", () => setActive(activeIndex - 1, { scroll: false }));
  gallery.querySelector("[data-gallery-dialog-next]")?.addEventListener("click", () => setActive(activeIndex + 1, { scroll: false }));
  gallery.querySelector("[data-gallery-close]")?.addEventListener("click", closeDialog);

  thumbnails.forEach((thumbnail, index) => thumbnail.addEventListener("click", () => setActive(index)));
  gallery.querySelectorAll("[data-gallery-open]").forEach((opener) => {
    opener.addEventListener("click", () => openDialog(Number(opener.dataset.galleryOpen || 0)));
  });

  track.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setActive(activeIndex - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setActive(activeIndex + 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActive(slides.length - 1);
    }
  });

  dialog?.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setActive(activeIndex - 1, { scroll: false });
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setActive(activeIndex + 1, { scroll: false });
    }
  });
  dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });

  track.addEventListener("scroll", () => {
    window.cancelAnimationFrame(scrollFrame);
    scrollFrame = window.requestAnimationFrame(() => {
      const target = track.scrollLeft;
      let closest = 0;
      let distance = Number.POSITIVE_INFINITY;
      slides.forEach((slide, index) => {
        const candidate = Math.abs(slide.offsetLeft - target);
        if (candidate < distance) {
          closest = index;
          distance = candidate;
        }
      });
      if (closest !== activeIndex) setActive(closest, { scroll: false });
    });
  }, { passive: true });

  setActive(0, { scroll: false });
})();
