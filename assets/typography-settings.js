(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function initTypographySettings() {
    apply();
    window.MEMORY_TYPOGRAPHY = { apply };
  });

  function apply() {
    const root = document.documentElement;
    const typography = window.MEMORY_BOOK?.meta?.typography || {};

    setPx(root, "--memory-event-date-size", typography.eventDatePx, 20, 64);
    setPx(root, "--memory-event-caption-size", typography.eventCaptionPx, 10, 32);

    const scale = finiteInRange(typography.polaroidCaptionScale, 60, 180);
    if (scale === null) {
      root.style.removeProperty("--memory-polaroid-caption-short-size");
      root.style.removeProperty("--memory-polaroid-caption-medium-size");
      root.style.removeProperty("--memory-polaroid-caption-long-size");
    } else {
      const ratio = scale / 100;
      root.style.setProperty("--memory-polaroid-caption-short-size", `${round(17.28 * ratio)}px`);
      root.style.setProperty("--memory-polaroid-caption-medium-size", `${round(13.76 * ratio)}px`);
      root.style.setProperty("--memory-polaroid-caption-long-size", `${round(11.04 * ratio)}px`);
    }
  }

  function setPx(root, property, value, min, max) {
    const number = finiteInRange(value, min, max);
    if (number === null) root.style.removeProperty(property);
    else root.style.setProperty(property, `${round(number)}px`);
  }

  function finiteInRange(value, min, max) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    return Math.min(max, Math.max(min, number));
  }

  function round(value) {
    return Math.round(value * 100) / 100;
  }
})();
