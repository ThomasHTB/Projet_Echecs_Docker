
class ChessSocket {
  constructor(url, handlers = {}) {
    this.url = url;
    this.handlers = handlers;
    this.socket = null;

    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 15000;
    this.reconnectTimer = null;
    this.manualClose = false;
  }

  connect() {
    if (
      this.socket &&
      [WebSocket.OPEN, WebSocket.CONNECTING].includes(
        this.socket.readyState
      )
    ) {
      return;
    }

    this.manualClose = false;

    try {
      this.socket = new WebSocket(this.url);
    } catch (error) {
      this.handlers.onError?.(error);
      this.scheduleReconnect();
      return;
    }

    this.socket.addEventListener("open", () => {
      this.reconnectDelay = 1000;
      this.handlers.onOpen?.();
    });

    this.socket.addEventListener("message", (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handlers.onMessage?.(message);
      } catch (error) {
        console.error("Message JSON invalide :", error);
      }
    });

    this.socket.addEventListener("error", (event) => {
      this.handlers.onError?.(event);
    });

    this.socket.addEventListener("close", () => {
      this.handlers.onClose?.();

      if (!this.manualClose) {
        this.scheduleReconnect();
      }
    });
  }

  send(message) {
    if (!this.socket ||
        this.socket.readyState !== WebSocket.OPEN) {
      return false;
    }

    this.socket.send(JSON.stringify(message));
    return true;
  }

  scheduleReconnect() {
    if (this.reconnectTimer || this.manualClose) return;

    const delay = this.reconnectDelay;

    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.maxReconnectDelay
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  disconnect() {
    this.manualClose = true;

    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;

    this.socket?.close();
  }
}