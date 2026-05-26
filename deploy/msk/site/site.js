const THEME_KEY = "memlayer-site-theme";
const themeToggle = document.getElementById("theme-toggle");
const body = document.body;

function resolveAutoTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(mode) {
  if (mode === "auto") {
    body.dataset.theme = resolveAutoTheme();
    body.dataset.themePreference = "auto";
    return;
  }
  body.dataset.theme = mode;
  body.dataset.themePreference = mode;
}

function loadTheme() {
  const saved = localStorage.getItem(THEME_KEY) || "auto";
  if (themeToggle) {
    themeToggle.value = saved;
  }
  applyTheme(saved);
}

function handleThemeChange(event) {
  const value = event.target.value;
  localStorage.setItem(THEME_KEY, value);
  applyTheme(value);
}

function bindCopyButtons() {
  document.querySelectorAll(".copy-button[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const targetId = button.getAttribute("data-copy-target");
      const source = document.getElementById(targetId);
      if (!source) {
        return;
      }
      await navigator.clipboard.writeText(source.textContent || "");
      const previous = button.textContent;
      button.textContent = "Copied";
      button.dataset.copied = "true";
      window.setTimeout(() => {
        button.textContent = previous;
        button.dataset.copied = "false";
      }, 1400);
    });
  });
}

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if ((localStorage.getItem(THEME_KEY) || "auto") === "auto") {
    applyTheme("auto");
  }
});

if (themeToggle) {
  themeToggle.addEventListener("change", handleThemeChange);
}

loadTheme();
bindCopyButtons();
