let img = document.getElementById("stream");
const select = document.getElementById("stream-select");
const fullscreenBtn = document.getElementById("fullscreen-btn");
const toggleModeBtn = document.getElementById("toggle-mode-btn");
const refreshBtn = document.getElementById("refresh-btn");
const streamContainer = document.getElementById("stream-container");
const overlay = document.getElementById("overlay");

let mode = "auto"; // "snapshot", "stream", "auto"
let status = "unloaded"; // "loaded", "unloaded"
let updateTimer = null;
let autoTimer = null;
let lastSnapshotURL = "";

const originalOptionTexts = Array.from(select.options).map(opt => opt.textContent);
let statusLoading = false;

const refreshStatus = document.getElementById("refresh-status");

async function checkStatuses() {
  if (statusLoading) return; // не дублируем запросы
  statusLoading = true;

  refreshStatus.style.display = "inline"; // показываем индикатор

  for (let i = 0; i < select.options.length; i++) {
    select.options[i].textContent = originalOptionTexts[i] + " ⏳";
    select.options[i].style.color = "gray";
  }

  await Promise.all(Array.from(select.options).map((option, i) =>
    fetch(`/proxy?url=${encodeURIComponent(option.value + "/objects")}`)
      .then(resp => {
        if (resp.ok) {
          option.textContent = originalOptionTexts[i] + " ✅";
          option.style.color = "lime";
        } else {
          option.textContent = originalOptionTexts[i] + " ❌";
          option.style.color = "red";
        }
      })
      .catch(() => {
        option.textContent = originalOptionTexts[i] + " ❌";
        option.style.color = "red";
      })
  ));

  statusLoading = false;
  refreshStatus.style.display = "none"; // скрываем индикатор
}

function showOverlay() {
  overlay.style.display = "flex";
  img.style.filter = "brightness(0.4)";
}
function hideOverlay() {
  overlay.style.display = "none";
  img.style.filter = "brightness(1)";
}

function startSnapshotLoop() {
  function update() {
    const urlBase = select.value;
    img.src = `${urlBase}/snapshot.jpg?t=${Date.now()}`;
  }
  update();
  img.onload = () => updateTimer = setTimeout(update, 100);
  img.onerror = () => updateTimer = setTimeout(update, 200);
}
function stopSnapshotLoop() {
  if (updateTimer) clearTimeout(updateTimer);
  updateTimer = null;
  img.onload = null;
  img.onerror = null;
}

function replaceStreamImage(newSrc) {
  if (img) {
    img.src = newSrc; // просто меняем картинку
  } else {
    const newImg = document.createElement("img");
    newImg.id = "stream";
    newImg.alt = "Live Stream";
    newImg.src = newSrc;
    Object.assign(newImg.style, {
      maxWidth: "100%",
      maxHeight: "100%",
      background: "#111",
      objectFit: "contain",
      userSelect: "none",
      pointerEvents: "none",
      transition: "filter 0.3s ease"
    });
    streamContainer.insertBefore(newImg, overlay);
    img = newImg;
  }
}

function updateImage() {
  const urlBase = select.value;
  if (mode === "snapshot") {
    stopAutoMode();
    startSnapshotLoop();
  } else if (mode === "stream") {
    stopAutoMode();
    stopSnapshotLoop();
    replaceStreamImage(`${urlBase}/current.jpg?t=${Date.now()}`);
  } else if (mode === "auto") {
    startAutoMode();
  }
}

function startAutoMode() {
  stopSnapshotLoop();
  if (autoTimer) clearInterval(autoTimer);
  const urlBase = select.value;
  function checkSnapshot() {
    const url = `${urlBase}/snapshot.jpg?t=${Date.now()}`;
    const probeImg = new Image();
    probeImg.onload = () => {
      if (status === "unloaded") {
        status = "loaded";
        hideOverlay();
        replaceStreamImage(`${urlBase}/current.jpg?t=${Date.now()}`);
      }
    };
    probeImg.onerror = () => {
      if (status === "loaded") {
        status = "unloaded";
        lastSnapshotURL = img.src;
        img.src = lastSnapshotURL;
        showOverlay();
      }
    };
    probeImg.src = url;
  }
  autoTimer = setInterval(checkSnapshot, 5000);
  checkSnapshot();
}
function stopAutoMode() {
  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
  }
  hideOverlay();
}

select.addEventListener("change", updateImage);

toggleModeBtn.addEventListener("click", () => {
  if (mode === "snapshot") {
    mode = "stream";
  } else if (mode === "stream") {
    mode = "auto";
  } else {
    mode = "snapshot";
  }
  toggleModeBtn.textContent = "Режим: " + (mode === "snapshot" ? "Слайдшоу" : mode === "stream" ? "Поток" : "Авто");
  updateImage();
});

fullscreenBtn.addEventListener("click", () => {
  if (!document.fullscreenElement) {
    streamContainer.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
});

document.addEventListener("fullscreenchange", () => {
  fullscreenBtn.textContent = document.fullscreenElement
    ? "Выйти из полноэкранного"
    : "Во весь экран";
});

refreshBtn.addEventListener("click", () => {
  const urlBase = select.value;
  if (mode === "snapshot") {
    updateImage();
  } else {
    stopSnapshotLoop();
    replaceStreamImage(`${urlBase}/current.jpg?t=${Date.now()}`);
  }

  checkStatuses();

  refreshBtn.disabled = true;
  setTimeout(() => refreshBtn.disabled = false, 1000);
});

toggleModeBtn.textContent = "Режим: Авто";
updateImage();

// Запускаем проверку сразу при открытии страницы
checkStatuses();
