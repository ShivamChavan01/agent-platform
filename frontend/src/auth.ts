import { api, ApiError, clearToken, getToken, setToken } from "./lib/api";
import type { TokenResponse, User } from "./lib/types";

export const USER_KEY = "aw_user";

export interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string | undefined, email: string, password: string) => Promise<void>;
  logout: () => void;
  updateUser: (user: User) => void;
  authed: boolean;
}

export function loadStoredAuth(): { user: User | null; token: string | null } {
  const token = getToken();
  const raw = localStorage.getItem(USER_KEY);
  let user: User | null = null;
  if (raw) {
    try {
      user = JSON.parse(raw) as User;
    } catch {
      user = null;
    }
  }
  return { user, token };
}

function persist(resp: TokenResponse): User {
  setToken(resp.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
  return resp.user;
}

export const authApi = {
  login: async (email: string, password: string): Promise<User> => {
    const resp = await api.post<TokenResponse>("/auth/login", { email, password });
    return persist(resp);
  },

  register: async (name: string | undefined, email: string, password: string): Promise<User> => {
    const resp = await api.post<TokenResponse>("/auth/register", { email, password, name });
    return persist(resp);
  },

  me: async (): Promise<User> => {
    const user = await api.get<User>("/auth/me");
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  },

  logout: (): void => {
    clearToken();
    localStorage.removeItem(USER_KEY);
  },

  isUnauthorized: (err: unknown): boolean => err instanceof ApiError && err.status === 401,
};
