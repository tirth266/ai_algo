import { API_BASE_URL } from './api';

interface AngelLoginRequest {
  totp: string;
}

interface AngelLoginResponse {
  status: string;
  message?: string;
  data?: {
    connected: boolean;
    jwt_token?: string;
    feed_token?: string;
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

  async autoLogin(): Promise<AngelLoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/angel/auto-login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.json();
  },

  async getStatus(): Promise<AngelStatusResponse> {
    const response = await fetch(`${API_BASE_URL}/api/angel/status`);
    return response.json();
  },

  async logout(): Promise<{ status: string; message?: string }> {
    const response = await fetch(`${API_BASE_URL}/api/angel/logout`, {
      method: 'POST',
    });
    return response.json();
  },

  async getProfile(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/angel/profile`);
    return response.json();
  },
};

export const ANGEL_STORAGE_KEY = 'angel_one_connected';

export const setAngelConnected = (connected: boolean) => {
  localStorage.setItem(ANGEL_STORAGE_KEY, connected ? 'true' : 'false');
};

export const getAngelConnected = (): boolean => {
  return localStorage.getItem(ANGEL_STORAGE_KEY) === 'true';
};

export const removeAngelConnected = () => {
  localStorage.removeItem(ANGEL_STORAGE_KEY);
};