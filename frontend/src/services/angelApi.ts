import { API_BASE_URL } from './api';

interface AngelLoginRequest {
  client_code: string;
  password: string;
  totp: string;
}

interface AngelLoginResponse {
  status: string;
  message?: string;
  data?: {
    jwt_token: string;
    feed_token: string;
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

export const ANGEL_STORAGE_KEY = 'angel_one_token';

export const setAngelToken = (token: string) => {
  localStorage.setItem(ANGEL_STORAGE_KEY, token);
};

export const getAngelToken = (): string | null => {
  return localStorage.getItem(ANGEL_STORAGE_KEY);
};

export const removeAngelToken = () => {
  localStorage.removeItem(ANGEL_STORAGE_KEY);
};

export const isAngelConnected = (): boolean => {
  return !!getAngelToken();
};