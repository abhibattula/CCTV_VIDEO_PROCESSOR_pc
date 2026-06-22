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

function setDomTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
}

let installed = false;

export function installTheme() {
  if (installed) return;
  installed = true;
  const saved = readStoredTheme();
  setDomTheme(saved); // apply only — no write-back of the value we just read
  const navBar = document.getElementById("app-nav");
  if (!navBar) return;
  const toggle = document.createElement("button");
  toggle.className = "theme-toggle";
  toggle.textContent = saved === "light" ? "🌙" : "☀️";
  toggle.title = "Toggle theme";
  toggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    setDomTheme(next);
    writeStoredTheme(next); // persist only on an actual user-initiated change
    toggle.textContent = next === "light" ? "🌙" : "☀️";
  });
  navBar.appendChild(toggle);
}
