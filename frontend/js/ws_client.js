class WSClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = { tick: [], market_update: [], sim_state: [] };
    this.reconnectTimer = null;
  }

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      this.scheduleReconnect();
      return;
    }
    this.ws.onopen = () => {
      this.onConnectionChange(true);
    };
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        (this.handlers[msg.type] || []).forEach(fn => fn(msg.data));
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };
    this.ws.onclose = () => {
      this.onConnectionChange(false);
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 2000);
  }

  on(eventType, callback) {
    if (!this.handlers[eventType]) {
      this.handlers[eventType] = [];
    }
    this.handlers[eventType].push(callback);
  }

  send(action) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action }));
    }
  }

  onConnectionChange(connected) {
    (this.handlers['connection'] || []).forEach(fn => fn(connected));
  }
}
