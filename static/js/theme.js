const KEY = "cctv-theme";

function readStoredTheme() {
  try {
    return localStorage.getItem(KEY) || "dark";
  } catch {
    return "dark"; // storage blocked — fall back to default, don't crash
  }
}

function writeStoredTheme(theme) {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // storage blocked — theme still applies for this session, just won't persist
  }
}

export function installTheme() {
  const saved = readStoredTheme();
  applyTheme(saved);
  const navBar = document.getElementById("app-nav");
  if (!navBar) return;
  const toggle = document.createElement("button");
  toggle.className = "theme-toggle";
  toggle.textContent = saved === "light" ? "🌙" : "☀️";
  toggle.title = "Toggle theme";
  toggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
    toggle.textContent = next === "light" ? "🌙" : "☀️";
  });
  navBar.appendChild(toggle);
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
  writeStoredTheme(theme);
}
