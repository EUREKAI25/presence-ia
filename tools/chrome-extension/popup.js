// PRESENCE_IA Evidence Capture — popup.js
// Manifest V3 — utilise chrome.tabs.captureVisibleTab + fetch vers l'API

let config = {
  server_url: "https://presence-ia.com",
  default_profession: "couvreur",
  default_city: "Rennes",
  admin_token: "changeme"
};

// Charger config.json au démarrage
fetch(chrome.runtime.getURL("config.json"))
  .then(r => r.json())
  .then(cfg => {
    config = { ...config, ...cfg };
    document.getElementById("profession").value = config.default_profession;
    document.getElementById("city").value = config.default_city;
  })
  .catch(() => {}); // fallback silencieux

// ── Helpers ───────────────────────────────────────────────────────────────

function setStatus(msg, type = "") {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = type;
}

function dataURLtoBlob(dataUrl) {
  const [header, data] = dataUrl.split(",");
  const mime = header.match(/:(.*?);/)[1];
  const binary = atob(data);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

// ── Capture & Upload ──────────────────────────────────────────────────────

document.getElementById("btn-capture").addEventListener("click", async () => {
  const provider   = document.getElementById("provider").value;
  const profession = document.getElementById("profession").value.trim().toLowerCase();
  const city       = document.getElementById("city").value.trim().toLowerCase();
  const btn        = document.getElementById("btn-capture");

  if (!profession || !city) {
    setStatus("Profession et ville requis.", "err");
    return;
  }

  btn.disabled = true;
  setStatus("Capture en cours…");

  try {
    // 1. Capturer screenshot de l'onglet visible
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });

    // 2. Convertir en Blob
    const blob = dataURLtoBlob(dataUrl);
    const filename = `screenshot.png`;

    // 3. Uploader vers l'API
    const formData = new FormData();
    formData.append("file", blob, filename);

    const url = new URL(`${config.server_url}/api/evidence/upload`);
    url.searchParams.set("profession", profession);
    url.searchParams.set("city", city);
    url.searchParams.set("provider", provider);

    const resp = await fetch(url.toString(), {
      method: "POST",
      body: formData,
      headers: {
        "X-Admin-Token": config.admin_token,
      },
    });

    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`HTTP ${resp.status} — ${err}`);
    }

    const data = await resp.json();
    const uploadedUrl = data.url;

    // 4. Afficher + copier
    setStatus(`✅ ${data.filename}`, "ok");
    document.getElementById("btn-copy").style.display = "block";

    document.getElementById("btn-copy").onclick = async () => {
      await navigator.clipboard.writeText(uploadedUrl);
      document.getElementById("btn-copy").textContent = "✅ Copié !";
      setTimeout(() => {
        document.getElementById("btn-copy").textContent = "📋 Copier l'URL";
      }, 1500);
    };

  } catch (err) {
    setStatus(`❌ ${err.message}`, "err");
  } finally {
    btn.disabled = false;
  }
});
