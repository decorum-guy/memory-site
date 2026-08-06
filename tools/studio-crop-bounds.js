(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function installCropAxisBounds() {
    if (typeof rebuildCropMedia !== "function" || typeof applyCropPosition !== "function") return;

    const baseRebuildCropMedia = rebuildCropMedia;
    const baseApplyCropPosition = applyCropPosition;
    let axes = { x: true, y: true };
    let boundMedia = null;

    rebuildCropMedia = function boundedRebuildCropMedia() {
      axes = { x: true, y: true };
      baseRebuildCropMedia();
      bindCurrentMedia();
    };

    applyCropPosition = function boundedApplyCropPosition() {
      constrainSession();
      baseApplyCropPosition();
      renderAxisState();
    };

    function bindCurrentMedia() {
      const media = cropStage.querySelector("[data-crop-media]");
      if (!media || media === boundMedia) return;
      boundMedia = media;
      const update = () => updateAxes(media);
      if (media.tagName === "VIDEO") {
        media.addEventListener("loadedmetadata", update);
        media.addEventListener("loadeddata", update);
        if (media.videoWidth && media.videoHeight) update();
      } else {
        media.addEventListener("load", update);
        if (media.complete && media.naturalWidth && media.naturalHeight) update();
      }
      requestAnimationFrame(update);
    }

    function updateAxes(media) {
      if (!cropSession || !media?.isConnected) return;
      const mediaWidth = media.tagName === "VIDEO" ? media.videoWidth : media.naturalWidth;
      const mediaHeight = media.tagName === "VIDEO" ? media.videoHeight : media.naturalHeight;
      if (!(mediaWidth > 0 && mediaHeight > 0)) return;

      const rect = cropStage.getBoundingClientRect();
      const stageRatio = rect.width > 0 && rect.height > 0 ? rect.width / rect.height : 4 / 3;
      const mediaRatio = mediaWidth / mediaHeight;
      const tolerance = .006;
      axes = {
        x: mediaRatio > stageRatio + tolerance,
        y: mediaRatio < stageRatio - tolerance,
      };
      constrainSession();
      baseApplyCropPosition();
      renderAxisState();
    }

    function constrainSession() {
      if (!cropSession) return;
      if (!axes.x) cropSession.crop.x = 50;
      if (!axes.y) cropSession.crop.y = 50;
    }

    function renderAxisState() {
      cropStage.classList.toggle("crop-stage--x-locked", !axes.x);
      cropStage.classList.toggle("crop-stage--y-locked", !axes.y);
      cropPosition.dataset.xLocked = axes.x ? "0" : "1";
      cropPosition.dataset.yLocked = axes.y ? "0" : "1";
      cropPosition.title = [
        axes.x ? "X можно менять" : "X зафиксирован: по горизонтали изображение уже полностью заполняет кадр",
        axes.y ? "Y можно менять" : "Y зафиксирован: по вертикали изображение уже полностью заполняет кадр",
      ].join(" · ");
    }

    new MutationObserver(bindCurrentMedia).observe(cropStage, { childList: true });
    window.addEventListener("resize", () => {
      if (boundMedia?.isConnected) updateAxes(boundMedia);
    });

    window.MEMORY_CROP_BOUNDS = {
      getState() {
        return { ...axes, xValue: cropSession?.crop?.x ?? null, yValue: cropSession?.crop?.y ?? null };
      },
    };
  });
})();
