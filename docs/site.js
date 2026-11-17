"use strict";

document.querySelectorAll(".animation").forEach((button) => {
  const image = button.querySelector("img");
  const label = button.querySelector(".play-label");
  const icon = button.querySelector(".play-icon");
  const title = image.alt;
  function stop() {
    image.src = button.dataset.poster;
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", `Play ${title}`);
    label.textContent = "Play animation";
    icon.textContent = "▶";
  }
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-pressed") === "true") {
      stop();
      return;
    }
    button.setAttribute("aria-pressed", "true");
    button.setAttribute("aria-busy", "true");
    button.setAttribute("aria-label", `Stop ${title}`);
    label.textContent = "Loading animation…";
    image.onload = () => {
      button.removeAttribute("aria-busy");
      if (button.getAttribute("aria-pressed") === "true") {
        label.textContent = "Stop animation";
        icon.textContent = "■";
      }
    };
    image.onerror = () => {
      image.onerror = null;
      stop();
      button.removeAttribute("aria-busy");
      label.textContent = "Try again";
    };
    image.src = button.dataset.gif;
  });
});

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-filter]").forEach((item) => {
      item.setAttribute("aria-pressed", String(item === button));
    });
    document.querySelectorAll(".rd-grid .media-card").forEach((card) => {
      const hidden = button.dataset.filter !== "all" && !card.classList.contains(button.dataset.filter);
      if (hidden && card.querySelector(".animation").getAttribute("aria-pressed") === "true") {
        card.querySelector(".animation").click();
      }
      card.hidden = hidden;
    });
  });
});

document.querySelectorAll("pre").forEach((block) => {
  const code = block.querySelector("code");
  if (!code || code.classList.contains("language-text")) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy-code";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy code example");
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = "Copied";
    } catch (_) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = "Selected";
    }
    window.setTimeout(() => { button.textContent = "Copy"; }, 1800);
  });
  block.prepend(button);
});
