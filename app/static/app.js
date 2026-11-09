const state = {
  missions: [],
  filter: "semua",
  activeMission: null,
};

const regionProfiles = {
  "Bojongloa Kaler": { elevasi_m: 8, impervious_pct: 85 },
  "Buahbatu": { elevasi_m: 15, impervious_pct: 70 },
  "Coblong": { elevasi_m: 30, impervious_pct: 45 },
  "Andir": { elevasi_m: 12, impervious_pct: 80 },
  "Astanaanyar": { elevasi_m: 10, impervious_pct: 82 },
  "Babakan Ciparay": { elevasi_m: 9, impervious_pct: 80 },
  "Bandung Kidul": { elevasi_m: 14, impervious_pct: 72 },
  "Bandung Kulon": { elevasi_m: 8, impervious_pct: 84 },
  "Batununggal": { elevasi_m: 18, impervious_pct: 68 },
  "Cibeunying Kaler": { elevasi_m: 22, impervious_pct: 60 },
  "Cibiru": { elevasi_m: 25, impervious_pct: 55 },
  "Cicendo": { elevasi_m: 20, impervious_pct: 65 },
  "Gedebage": { elevasi_m: 7, impervious_pct: 78 },
  "Kiaracondong": { elevasi_m: 16, impervious_pct: 72 },
  "Lengkong": { elevasi_m: 11, impervious_pct: 85 },
  "Rancasari": { elevasi_m: 12, impervious_pct: 74 },
  "Regol": { elevasi_m: 10, impervious_pct: 83 },
  "Sukajadi": { elevasi_m: 24, impervious_pct: 62 },
  "Sumur Bandung": { elevasi_m: 14, impervious_pct: 86 },
  "Ujungberung": { elevasi_m: 28, impervious_pct: 50 },
};

const presets = {
  hujan: { field: "curah_hujan_mm", values: { ringan: 40, sedang: 90, lebat: 160, ekstrem: 250 } },
  air: { field: "tma_cm", values: { normal: 120, naik: 220, tinggi: 320, kritis: 430 } },
  drainase: { field: "drainase_skor", values: { lancar: 9, cukup: 6, tersumbat: 3, buruk: 1 } },
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (character) => {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return map[character];
  });

const formatDate = (iso) => {
  if (!iso) return "Tidak diketahui";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Tidak diketahui";
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
};

function setRangeValue(form, name, value) {
  const input = form.elements.namedItem(name);
  if (!input) return;
  input.value = String(value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function applyRegionProfile(form) {
  const select = form.elements.namedItem("wilayah");
  if (!select) return;
  const profile = regionProfiles[select.value] || regionProfiles["Bojongloa Kaler"];
  setRangeValue(form, "elevasi_m", profile.elevasi_m);
  setRangeValue(form, "impervious_pct", profile.impervious_pct);
  const note = $("#region-profile");
  if (note) {
    note.textContent = `Profil ${select.value}: elevasi sekitar ${profile.elevasi_m} m, permukaan kedap air sekitar ${profile.impervious_pct}%. Bisa diubah di mode ahli.`;
  }
}

function applyPreset(form, group) {
  const preset = presets[group];
  if (!preset) return;
  const selected = form.querySelector(`input[name="${group}_preset"]:checked`);
  if (!selected) return;
  setRangeValue(form, preset.field, preset.values[selected.value]);
}

class ApiError extends Error {
  constructor(message, payload) {
    super(message);
    this.payload = payload;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = data && data.detail !== undefined ? data.detail : data;
    const message =
      typeof detail === "string"
        ? detail
        : detail && detail.message
          ? detail.message
          : "Permintaan gagal diproses";
    throw new ApiError(message, detail);
  }
  return data;
}

let toastTimer = null;
function toast(message, type = "success") {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    element.className = "toast";
  }, 4200);
}

async function loadHealth() {
  const pill = $("#health-pill");
  try {
    const data = await api("/health");
    const checks = data.checks || {};
    const allOk = Object.values(checks).every((value) => value === "ok");
    pill.className = `health-pill ${allOk ? "ok" : "bad"}`;
    pill.innerHTML = `<span class="dot"></span> ${
      allOk ? "Sistem siap" : "Gangguan sistem"
    }`;
  } catch {
    pill.className = "health-pill bad";
    pill.innerHTML = `<span class="dot"></span> Offline`;
  }
}

async function loadStats() {
  try {
    const data = await api("/api/statistik");
    $("#stat-misi").textContent = data.misi_dibuka ?? "0";
    $("#stat-relawan").textContent = data.total_relawan ?? "0";
    $("#stat-prediksi").textContent = data.total_prediksi ?? "0";
    $("#stat-harian").textContent = data.prediksi_24_jam ?? "0";
  } catch {
    /* biarkan nilai terakhir */
  }
}

function missionCard(misi) {
  const skills = (misi.keahlian || [])
    .map((skill) => `<span class="chip needed">${escapeHtml(skill)}</span>`)
    .join("");
  const kebutuhan = (misi.kebutuhan || [])
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");

  const bisaGabung = misi.status === "dibuka" && misi.sisa_kuota > 0;
  const tombol = bisaGabung
    ? `<button class="primary small join-btn" type="button" data-id="${misi.id}">Gabung</button>`
    : `<button class="primary small" type="button" disabled>${
        misi.status === "penuh" ? "Kuota penuh" : "Ditutup"
      }</button>`;

  return `
    <article class="mission-card" id="misi-${misi.id}">
      <div class="mission-top">
        <div>
          <h3 class="mission-title">${escapeHtml(misi.judul)}</h3>
          <div class="mission-meta">
            <span>${escapeHtml(misi.wilayah)}</span>
            <span>${escapeHtml(misi.jenis_bencana)}</span>
            <span>${formatDate(misi.dibuat_pada)}</span>
          </div>
        </div>
        <span class="level-badge level-${escapeHtml(
          misi.level_risiko
        )}">${escapeHtml(misi.level_risiko)}</span>
      </div>
      <p class="mission-desc">${escapeHtml(misi.deskripsi)}</p>
      <div class="chips">${kebutuhan}</div>
      <div class="chips" style="margin-top: 7px">${skills}</div>
      <div class="mission-progress">
        <div class="progress-labels">
          <span>${misi.relawan_terdaftar} dari ${misi.kuota} relawan</span>
          <span>${misi.sisa_kuota} slot tersisa</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: ${Math.min(
            misi.progres_pct,
            100
          )}%"></div>
        </div>
      </div>
      <div class="mission-footer">
        <span class="status-pill ${misi.status === "penuh" ? "penuh" : ""}">${escapeHtml(
          misi.status
        )}</span>
        ${tombol}
      </div>
    </article>
  `;
}

function renderMissions() {
  const container = $("#mission-list");
  let data = [...state.missions];

  if (state.filter === "Awas" || state.filter === "Siaga") {
    data = data.filter((misi) => misi.level_risiko === state.filter);
  } else if (state.filter === "dibuka") {
    data = data.filter((misi) => misi.status === "dibuka");
  }

  $("#mission-count").textContent = `${data.length} misi`;

  if (!data.length) {
    container.innerHTML = `<div class="empty-state">Belum ada misi pada filter ini. Jalankan prediksi berisiko Siaga/Awas untuk membuka misi.</div>`;
    return;
  }
  container.innerHTML = data.map(missionCard).join("");
}

async function loadMissions() {
  try {
    state.missions = await api("/api/misi");
    renderMissions();
  } catch {
    $("#mission-list").innerHTML = `<div class="empty-state">Gagal memuat papan misi. Coba muat ulang.</div>`;
  }
}

function renderHistory(items) {
  const body = $("#history-body");
  if (!items || !items.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty-cell">Belum ada prediksi.</td></tr>`;
    return;
  }

  body.innerHTML = items
    .map((item) => {
      const misi = item.misi
        ? `<a class="ghost-link small" href="#misi-${item.misi.id}">Lihat</a>`
        : `<span class="chip">Tidak ada</span>`;
      return `
        <tr>
          <td>${formatDate(item.dibuat_pada)}</td>
          <td class="wilayah">${escapeHtml(item.wilayah)}</td>
          <td>${Number(item.curah_hujan_mm).toLocaleString("id-ID")} mm</td>
          <td>${Number(item.tma_cm).toLocaleString("id-ID")} cm</td>
          <td><span class="level-badge level-${escapeHtml(item.level)}">${escapeHtml(
            item.level
          )}</span></td>
          <td>${item.skor_risiko}</td>
          <td>${misi}</td>
        </tr>
      `;
    })
    .join("");
}

async function loadHistory() {
  try {
    const items = await api("/api/prediksi?limit=12");
    renderHistory(items);
  } catch {
    $("#history-body").innerHTML = `<tr><td colspan="7" class="empty-cell">Gagal memuat riwayat.</td></tr>`;
  }
}

function newsCard(item) {
  const image = item.image
    ? `<img class="news-image" src="${escapeHtml(item.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" />`
    : "";
  const published = item.published ? formatDate(item.published) : "Waktu tidak tersedia";
  return `
    <article class="news-card">
      ${image}
      <div class="news-body">
        <div class="news-meta">
          <span>${escapeHtml(item.source)}</span>
          <span>${escapeHtml(published)}</span>
        </div>
        <h3 class="news-title">${escapeHtml(item.title)}</h3>
        <p class="news-summary">${escapeHtml(item.summary)}</p>
        <a class="news-link" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer">Baca di sumber</a>
      </div>
    </article>
  `;
}

function renderNews(items) {
  const container = $("#news-list");
  if (!items || !items.length) {
    container.innerHTML = `<div class="news-empty">Berita belum tersedia. <a href="https://news.google.com/search?q=banjir%20Indonesia&hl=id" target="_blank" rel="noreferrer">Cek Google News</a>.</div>`;
    return;
  }
  container.innerHTML = items.map(newsCard).join("");
  $$("#news-list .news-image").forEach((image) => {
    image.addEventListener("error", () => image.remove());
  });
}

async function loadNews() {
  const button = $("#refresh-news");
  if (button) button.disabled = true;
  $("#news-list").innerHTML = `<div class="news-empty">Memuat berita…</div>`;
  try {
    const items = await api("/api/berita");
    renderNews(items);
  } catch {
    $("#news-list").innerHTML = `<div class="news-empty">Berita belum bisa dimuat. <a href="https://news.google.com/search?q=banjir%20Indonesia&hl=id" target="_blank" rel="noreferrer">Cek Google News</a>.</div>`;
  } finally {
    if (button) button.disabled = false;
  }
}

function renderResult(data) {
  const result = $("#prediction-result");
  result.classList.remove("hidden");

  $("#result-score").textContent = data.skor_risiko;

  const skor = Math.min(Math.max(Number(data.skor_risiko) || 0, 0), 100);
  const marker = $("#risk-marker");
  marker.style.left = `${skor}%`;
  marker.dataset.level = data.level;
  $$("#risk-scale [data-level]").forEach((segment) => {
    segment.classList.toggle("active", segment.dataset.level === data.level);
  });

  $("#result-title").textContent = `Risiko ${data.level} di ${data.wilayah}`;
  $("#result-recommendation").textContent = data.rekomendasi;

  $("#result-factors").innerHTML = (data.faktor || [])
    .map(
      (factor) =>
        `<span class="factor"><strong>${escapeHtml(factor.nama)}</strong> ${escapeHtml(
          factor.nilai
        )}, ${escapeHtml(factor.keterangan)}</span>`
    )
    .join("");

  const missionBox = $("#mission-created");
  if (data.misi) {
    missionBox.classList.remove("hidden");
    $("#mission-created-text").textContent = `${data.misi.judul}. Kuota ${data.misi.kuota} relawan. ${data.misi.keahlian.length} keahlian dibutuhkan.`;
  } else {
    missionBox.classList.add("hidden");
  }

  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

function readPredictionPayload(form) {
  const data = new FormData(form);
  return {
    wilayah: String(data.get("wilayah") || "").trim(),
    curah_hujan_mm: Number(data.get("curah_hujan_mm")),
    tma_cm: Number(data.get("tma_cm")),
    drainase_skor: Number(data.get("drainase_skor")),
    elevasi_m: Number(data.get("elevasi_m")),
    impervious_pct: Number(data.get("impervious_pct")),
  };
}

async function submitPrediction(event) {
  event.preventDefault();
  const button = $("#predict-button");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Menghitung…";

  try {
    const payload = readPredictionPayload(event.currentTarget);
    const data = await api("/api/prediksi", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderResult(data);
    await Promise.all([loadMissions(), loadStats(), loadHistory()]);
    toast(
      data.misi
        ? `Risiko ${data.level}. ${data.misi.judul} dibuka.`
        : `Risiko ${data.level}. Belum perlu membuka misi.`,
      "success"
    );
  } catch (error) {
    toast(error.message || "Gagal menghitung risiko", "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function updateRangeOutputs(form) {
  const map = [
    ["curah_hujan_mm", "#rain-value", (value) => `${value} mm`],
    ["tma_cm", "#tma-value", (value) => `${value} cm`],
    ["drainase_skor", "#drainase-value", (value) => `${value}/10`],
    ["elevasi_m", "#elevasi-value", (value) => `${value} m`],
    ["impervious_pct", "#impervious-value", (value) => `${value}%`],
  ];
  map.forEach(([name, selector, format]) => {
    const input = form.elements.namedItem(name);
    const output = $(selector);
    if (input && output) output.textContent = format(input.value);
  });
}

function openJoinModal(misi) {
  state.activeMission = misi;
  $("#modal-title").textContent = misi.judul;
  $("#modal-desc").textContent = misi.deskripsi;
  $("#modal-skills").innerHTML = (misi.keahlian || [])
    .map((skill) => `<span class="chip needed">${escapeHtml(skill)}</span>`)
    .join("");

  const form = $("#join-form");
  form.elements.namedItem("misi_id").value = misi.id;
  form.elements.namedItem("keahlian").value = (misi.keahlian || []).slice(0, 2).join(", ");

  $("#join-modal").classList.remove("hidden");
  form.elements.namedItem("nama").focus();
}

function closeJoinModal() {
  $("#join-modal").classList.add("hidden");
  state.activeMission = null;
}

async function submitJoin(event) {
  event.preventDefault();
  if (!state.activeMission) return;

  const form = event.currentTarget;
  const button = $("#join-button");
  const original = button.textContent;
  const data = new FormData(form);
  const keahlian = String(data.get("keahlian") || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  if (!keahlian.length) {
    toast("Isi minimal satu keahlian", "error");
    return;
  }

  button.disabled = true;
  button.textContent = "Mengirim…";

  try {
    const response = await api(`/api/misi/${state.activeMission.id}/gabung`, {
      method: "POST",
      body: JSON.stringify({
        nama: String(data.get("nama") || "").trim(),
        kontak: String(data.get("kontak") || "").trim(),
        keahlian,
      }),
    });
    closeJoinModal();
    form.reset();
    toast(
      `Berhasil bergabung. ${response.misi.relawan_terdaftar}/${response.misi.kuota} relawan terdaftar.`,
      "success"
    );
    await Promise.all([loadMissions(), loadStats()]);
  } catch (error) {
    const dibutuhkan = error.payload && error.payload.keahlian_dibutuhkan;
    const pesan = dibutuhkan
      ? `${error.message}. Dibutuhkan: ${dibutuhkan.join(", ")}`
      : error.message || "Gagal mendaftar";
    toast(pesan, "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function bindEvents() {
  const form = $("#prediction-form");
  updateRangeOutputs(form);
  form.addEventListener("input", () => updateRangeOutputs(form));
  form.addEventListener("change", (event) => {
    const target = event.target;
    if (target.name === "wilayah") applyRegionProfile(form);
    if (target.name === "hujan_preset") applyPreset(form, "hujan");
    if (target.name === "air_preset") applyPreset(form, "air");
    if (target.name === "drainase_preset") applyPreset(form, "drainase");
  });
  form.addEventListener("submit", submitPrediction);
  applyRegionProfile(form);
  applyPreset(form, "hujan");
  applyPreset(form, "air");
  applyPreset(form, "drainase");
  updateRangeOutputs(form);

  $$(".filter").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".filter").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.filter = button.dataset.filter;
      renderMissions();
    });
  });

  $("#mission-list").addEventListener("click", (event) => {
    const button = event.target.closest(".join-btn");
    if (!button) return;
    const misi = state.missions.find((item) => item.id === Number(button.dataset.id));
    if (misi) openJoinModal(misi);
  });

  $("#modal-close").addEventListener("click", closeJoinModal);
  $("#join-modal").addEventListener("click", (event) => {
    if (event.target === $("#join-modal")) closeJoinModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeJoinModal();
  });
  $("#join-form").addEventListener("submit", submitJoin);
  $("#refresh-history").addEventListener("click", loadHistory);
  $("#refresh-news").addEventListener("click", loadNews);
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadHealth();
  loadStats();
  loadMissions();
  loadHistory();
  loadNews();

  setInterval(() => {
    loadHealth();
    loadMissions();
    loadStats();
  }, 20000);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadHealth();
      loadMissions();
      loadStats();
    }
  });
});
