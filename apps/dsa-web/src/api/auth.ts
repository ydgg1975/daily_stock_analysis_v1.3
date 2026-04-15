import apiClient from './index';

export type CurrentUser = {
  id: string;
  username: string;
  displayName?: string | null;
  role: 'admin' | 'user' | string;
  isAdmin: boolean;
  isAuthenticated: boolean;
  transitional: boolean;
  authEnabled: boolean;
  legacyAdmin?: boolean;
};

export type AuthStatusResponse = {
  authEnabled: boolean;
  loggedIn: boolean;
  passwordSet?: boolean;
  passwordChangeable?: boolean;
  setupState: 'enabled' | 'password_retained' | 'no_password';
  currentUser?: CurrentUser | null;
};

export type VerifyAdminPasswordResponse = {
  ok: boolean;
  unlockToken: string;
  expiresInSeconds: number;
};

export type UserNotificationPreferences = {
  channel: 'email' | 'discord' | 'multi' | string;
  enabled: boolean;
  email?: string | null;
  emailEnabled: boolean;
  discordEnabled: boolean;
  discordWebhook?: string | null;
  deliveryAvailable: boolean;
  emailDeliveryAvailable: boolean;
  discordDeliveryAvailable: boolean;
  updatedAt?: string | null;
};

export const authApi = {
  async getStatus(): Promise<AuthStatusResponse> {
    const { data } = await apiClient.get<AuthStatusResponse>('/api/v1/auth/status');
    return data;
  },

  async updateSettings(
    authEnabled: boolean,
    password?: string,
    passwordConfirm?: string,
    currentPassword?: string
  ): Promise<AuthStatusResponse> {
    const body: {
      authEnabled: boolean;
      password?: string;
      passwordConfirm?: string;
      currentPassword?: string;
    } = { authEnabled };
    if (password !== undefined) {
      body.password = password;
    }
    if (passwordConfirm !== undefined) {
      body.passwordConfirm = passwordConfirm;
    }
    if (currentPassword !== undefined) {
      body.currentPassword = currentPassword;
    }
    const { data } = await apiClient.post<AuthStatusResponse>('/api/v1/auth/settings', body);
    return data;
  },

  async getCurrentUser(): Promise<CurrentUser> {
    const { data } = await apiClient.get<CurrentUser>('/api/v1/auth/me');
    return data;
  },

  async getNotificationPreferences(): Promise<UserNotificationPreferences> {
    const { data } = await apiClient.get<UserNotificationPreferences>('/api/v1/auth/preferences/notifications');
    return data;
  },

  async updateNotificationPreferences(
    payload: {
      enabled?: boolean;
      email?: string | null;
      emailEnabled?: boolean;
      discordEnabled?: boolean;
      discordWebhook?: string | null;
    },
  ): Promise<UserNotificationPreferences> {
    const body = {
      enabled: payload.enabled ?? payload.emailEnabled ?? false,
      email: payload.email ?? null,
      emailEnabled: payload.emailEnabled ?? payload.enabled ?? false,
      discordEnabled: payload.discordEnabled ?? false,
      discordWebhook: payload.discordWebhook ?? null,
    };
    const { data } = await apiClient.put<UserNotificationPreferences>('/api/v1/auth/preferences/notifications', body);
    return data;
  },

  async login(params: {
    username?: string;
    displayName?: string;
    password: string;
    passwordConfirm?: string;
    createUser?: boolean;
  }): Promise<void> {
    const body: {
      username?: string;
      displayName?: string;
      password: string;
      passwordConfirm?: string;
      createUser?: boolean;
    } = {
      username: params.username,
      displayName: params.displayName,
      password: params.password,
      createUser: params.createUser,
    };
    if (params.passwordConfirm !== undefined) {
      body.passwordConfirm = params.passwordConfirm;
    }
    await apiClient.post('/api/v1/auth/login', body);
  },

  async verifyAdminPassword(
    password: string,
    passwordConfirm?: string
  ): Promise<VerifyAdminPasswordResponse> {
    const body: { password: string; passwordConfirm?: string } = { password };
    if (passwordConfirm !== undefined) {
      body.passwordConfirm = passwordConfirm;
    }
    const { data } = await apiClient.post<VerifyAdminPasswordResponse>('/api/v1/auth/verify-password', body);
    return data;
  },

  async changePassword(
    currentPassword: string,
    newPassword: string,
    newPasswordConfirm: string
  ): Promise<void> {
    await apiClient.post('/api/v1/auth/change-password', {
      currentPassword,
      newPassword,
      newPasswordConfirm,
    });
  },

  async logout(): Promise<void> {
    await apiClient.post('/api/v1/auth/logout');
  },
};
