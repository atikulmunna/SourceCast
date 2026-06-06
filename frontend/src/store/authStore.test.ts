import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import { useAuthStore } from "./authStore";

vi.mock("@/lib/api", () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
  setSessionExpiredHandler: vi.fn(),
}));

const mockedApi = vi.mocked(api);

describe("authStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: true,
    });
    vi.stubGlobal("window", { __sourcecast_access_token: undefined });
  });

  it("uses the login response user without a follow-up profile request", async () => {
    const user = {
      id: "user-1",
      email: "researcher@example.com",
      name: "Researcher",
      role: "USER",
      created_at: "2026-06-06T00:00:00Z",
    };
    mockedApi.post.mockResolvedValueOnce({
      data: {
        access_token: "access-token",
        token_type: "Bearer",
        expires_in: 3600,
        user,
      },
    });

    await useAuthStore.getState().login("researcher@example.com", "research123");

    expect(mockedApi.post).toHaveBeenCalledWith("/auth/login", {
      email: "researcher@example.com",
      password: "research123",
    });
    expect(mockedApi.get).not.toHaveBeenCalledWith("/auth/me");
    expect(window.__sourcecast_access_token).toBe("access-token");
    expect(useAuthStore.getState()).toMatchObject({
      user,
      isAuthenticated: true,
      isLoading: false,
    });
  });
});
