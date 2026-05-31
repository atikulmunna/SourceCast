"use client";

import { create } from "zustand";
import api from "@/lib/api";
import { User, TokenResponse } from "@/lib/types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  initialize: async () => {
    try {
      // Attempt silent refresh on app load to restore session
      const { data } = await api.post<TokenResponse>("/auth/refresh");
      if (typeof window !== "undefined") {
        window.__sourcecast_access_token = data.access_token;
      }
      const { data: user } = await api.get<User>("/auth/me");
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  login: async (email: string, password: string) => {
    const { data } = await api.post<TokenResponse>("/auth/login", {
      email,
      password,
    });
    if (typeof window !== "undefined") {
      window.__sourcecast_access_token = data.access_token;
    }
    const { data: user } = await api.get<User>("/auth/me");
    set({ user, isAuthenticated: true });
  },

  register: async (email: string, password: string, name?: string) => {
    await api.post("/auth/register", { email, password, name });
    // After register, log in automatically
    await get().login(email, password);
  },

  logout: async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      if (typeof window !== "undefined") {
        window.__sourcecast_access_token = undefined;
      }
      set({ user: null, isAuthenticated: false });
    }
  },
}));
