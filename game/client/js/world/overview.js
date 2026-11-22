// The overview uses the local world state. It shows the campus, the own
// player and their open stations, regardless of what other players are doing.

(function () {
  "use strict";

  const dialog = document.getElementById("campus-overview");
  const canvas = document.getElementById("overview-map");
  const openButton = document.getElementById("overview-open");
  const closeButton = document.getElementById("overview-close");
  const location = document.getElementById("overview-location");
  const taskList = document.getElementById("overview-list");
  const empty = document.getElementById("overview-empty");
  const context = canvas.getContext("2d");
  let background;
  let paintedCampus;
  let shownTasks;
  let phase;

  function updateBackground(campus) {
    if (paintedCampus === campus) return;
    background = document.createElement("canvas");
    background.width = canvas.width = campus.width;
    background.height = canvas.height = campus.height;
    Game.world.drawOverviewBase(background.getContext("2d"), campus);
    paintedCampus = campus;
    shownTasks = null;
  }

  function circle(x, y, radius, fill, outline, width) {
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fillStyle = fill;
    context.fill();
    context.strokeStyle = outline;
    context.lineWidth = width;
    context.stroke();
  }

  function drawMarkers(position, stations) {
    if (position) {
      circle(position.x, position.y, 16, "#3478BE", "#2E2A3B", 3);
      circle(position.x, position.y, 6, "#FFFFFF", "#FFFFFF", 1);
    }

    context.font = "bold 16px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    for (const station of stations) {
      circle(station.x, station.y, 12, "#FFD23F", "#2E2A3B", 2);
      context.fillStyle = "#2E2A3B";
      context.fillText(String(station.id), station.x, station.y);
    }
  }

  function showTasks(stations) {
    const signature = stations.map((station) => station.id).join(",");
    if (signature === shownTasks) return;
    shownTasks = signature;
    empty.hidden = stations.length > 0;
    taskList.replaceChildren(...stations.map((station) => {
      const item = document.createElement("li");
      const number = document.createElement("span");
      number.className = "overview-task-number";
      number.textContent = station.id;
      item.append(number, station.name);
      return item;
    }));
  }

  function render() {
    if (!dialog.open) return;
    const data = Game.world.overviewData();
    if (!data) {
      close();
      return;
    }
    const { campus, position, stations } = data;
    updateBackground(campus);
    const tasks = stations.map((id) => campus.stations.find((station) => station.id === id)).filter(Boolean);
    context.drawImage(background, 0, 0);
    drawMarkers(position, tasks);
    const room = position && Game.world.roomAt(campus, position.x, position.y);
    const place = !position ? "Locating you…" : "You · " + (room ? room.name : campus.deck_label.name);
    if (location.textContent !== place) location.textContent = place;
    showTasks(tasks);
  }

  function open() {
    if (dialog.open || Game.screens.current() !== "lobby" || !Game.world.overviewData()) return;
    if (document.querySelector(
      "#countdown:not([hidden]), #minigame:not([hidden]), #duel-ranking:not([hidden]), " +
      "#classic-meeting:not([hidden]), #classic-role-card:not([hidden]), #classic-end-screen:not([hidden])"
    )) return;
    Game.world.setOverviewOpen(true);
    dialog.showModal();
    render();
  }

  function close() {
    if (!dialog.open) return;
    dialog.close();
    Game.world.setOverviewOpen(false);
  }

  openButton.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });
  window.addEventListener("keydown", (event) => {
    if (event.code !== "KeyM" || event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    const target = event.target;
    if (target instanceof HTMLElement && (target.isContentEditable || target.matches("input, textarea, select"))) return;
    if (dialog.open) close();
    else open();
  });

  // Render after the existing game handlers have applied the same message.
  function refresh() {
    if (dialog.open) queueMicrotask(render);
  }

  Game.net.on("lobby_state", (message) => {
    if (message.phase !== phase) close();
    phase = message.phase;
    refresh();
  });
  ["positions", "station_done", "duel_state"].forEach((type) => Game.net.on(type, refresh));
  ["close", "left_lobby", "signed_out", "station_opened", "classic_role",
    "meeting_state", "classic_result", "duel_result"].forEach((type) => Game.net.on(type, close));
})();
