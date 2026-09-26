export const API_URL = "http://localhost:8000";
export const WS_URL = "ws://localhost:8000/api/ws/agent";

export const fetchWithConfig = async (endpoint, options = {}) => {
  const token = sessionStorage.getItem('token');
  const headers = { ...options.headers };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  // Ensure prefix /api if endpoint starts with /
  const url = endpoint.startsWith('/api') 
    ? `${API_URL}${endpoint}` 
    : (endpoint.startsWith('/') ? `${API_URL}/api${endpoint}` : `${API_URL}/api/${endpoint}`);

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem('token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "API request failed");
  }

  return response.json();
};

export const createAgentWebSocket = (onMessage, onOpen, onClose) => {
  try {
    const ws = new WebSocket(WS_URL);
    if (onOpen) ws.onopen = onOpen;
    if (onClose) ws.onclose = onClose;
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (err) {
        console.error("WS Parse error:", err);
      }
    };
    return ws;
  } catch (err) {
    console.warn("WebSocket connection not available:", err);
    return null;
  }
};
