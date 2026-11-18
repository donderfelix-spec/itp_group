// Connects to the server and shows whether the connection works.
// The game itself is added on top of this in the next milestones.

const statusElement = document.getElementById('status');
let retryDelay = 1000;

function showStatus(text, kind) {
  statusElement.textContent = text;
  statusElement.className = 'status status-' + kind;
}

function connect() {
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(scheme + '//' + location.host + '/ws');

  socket.addEventListener('open', () => {
    retryDelay = 1000;
    socket.send(JSON.stringify({ type: 'hello', name: 'Guest' + Math.floor(1000 + Math.random() * 9000) }));
  });

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'welcome') showStatus('Connected to the server', 'ok');
    if (message.type === 'error') showStatus(message.message, 'error');
  });

  socket.addEventListener('close', () => {
    showStatus('Connection lost. Reconnecting…', 'error');
    setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 10000);
  });
}

connect();
