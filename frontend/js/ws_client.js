// Resilient WebSocket client: exponential backoff, heartbeat, typed handlers.

export class WSClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = new Map();
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.attempt = 0;
    this.closedByUser = false;
    this.lastMessageAt = 0;
  }

  on(type, callback) {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type).push(callback);
    return this;
  }

  emit(type, data) {
    for (const fn of this.handlers.get(type) || []) {
      try {
        fn(data);
      } catch (error) {
        console.error(`ws handler ${type} failed`, error);
      }
    }
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.closedByUser = false;
    this.emit('status', { state: 'connecting' });

    let socket;
    try {
      socket = new WebSocket(this.url);
    } catch (error) {
      this.scheduleReconnect();
      return;
    }
    this.ws = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.lastMessageAt = Date.now();
      this.emit('status', { state: 'open' });
      this.startHeartbeat();
    };

    socket.onmessage = (event) => {
      this.lastMessageAt = Date.now();
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === 'pong') return;
      this.emit(message.type, message.data);
    };

    socket.onclose = () => {
      this.stopHeartbeat();
      this.emit('status', { state: 'closed' });
      if (!this.closedByUser) this.scheduleReconnect();
    };

    socket.onerror = () => {
      try {
        socket.close();
      } catch {
        /* noop */
      }
    };
  }

  scheduleReconnect() {
    if (this.reconnectTimer || this.closedByUser) return;
    const delay = Math.min(15_000, 1_000 * 2 ** this.attempt) + Math.random() * 400;
    this.attempt += 1;
    this.emit('status', { state: 'reconnecting', delay });
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      // If the server has gone quiet for over a minute, force a reconnect.
      if (Date.now() - this.lastMessageAt > 60_000) {
        try {
          this.ws.close();
        } catch {
          /* noop */
        }
        return;
      }
      this.send('ping');
    }, 20_000);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  send(action) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify({ action }));
    return true;
  }

  close() {
    this.closedByUser = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        /* noop */
      }
    }
  }
}
