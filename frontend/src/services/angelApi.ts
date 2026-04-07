import { API_BASE_URL } from './api';

interface AngelLoginRequest {
  totp: string;
}

interface AngelLoginResponse {
  status: string;
  message?: string;
  data?: {
    connected: boolean;
  };
  success?: boolean;
}

interface AngelStatusResponse {
  status: string;
  data: {
    authenticated: boolean;
    api_key_set: boolean;
    client_id: string | null;
    user_name: string | null;
  };
}

export const angelService = {
  async login(credentials: AngelLoginRequest): Promise<AngelLoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/angel/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    });
    return response.json();
  },

  async getStatus(): Promise<AngelStatusResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/angel/status`);
      return response.json();
    } catch (error) {
      return {
        status: 'error',
        data: {
          authenticated: false,
          api_key_set: false,
          client_id: null,
          user_name: null,
        },
      };
    }
  },

  async logout(): Promise<{ status: string; message?: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/angel/logout`, {
        method: 'POST',
      });
      return response.json();
    } catch (error) {
      return { status: 'success', message: 'Logged out locally' };
    }
  },
};

const ANGEL_CONNECTED_KEY = 'angel_one_connected';
const ANGEL_EXPIRY_KEY = 'angel_one_expiry';

export const setAngelConnected = (connected: boolean): void => {
  localStorage.setItem(ANGEL_CONNECTED_KEY, connected ? 'true' : 'false');
};

export const getAngelConnected = (): boolean => {
  return localStorage.getItem(ANGEL_CONNECTED_KEY) === 'true';
};

export const removeAngelConnected = (): void => {
  localStorage.removeItem(ANGEL_CONNECTED_KEY);
  localStorage.removeItem(ANGEL_EXPIRY_KEY);
};

export const setSessionExpiry = (timestamp: number): void => {
  localStorage.setItem(ANGEL_EXPIRY_KEY, timestamp.toString());
};

export const getSessionExpiry = (): number | null => {
  const expiry = localStorage.getItem(ANGEL_EXPIRY_KEY);
  return expiry ? parseInt(expiry, 10) : null;
};

export const isSessionValid = (): boolean => {
  const connected = getAngelConnected();
  const expiry = getSessionExpiry();
  
  if (!connected || !expiry) return false;
  return Date.now() < expiry;
};