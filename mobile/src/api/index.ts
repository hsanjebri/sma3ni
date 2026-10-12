import * as SecureStore from 'expo-secure-store';

import { createApi, type TokenStore } from './client';

export { ApiError, type ApiErrorCode } from './client';
export type * from './types';

// EXPO_PUBLIC_API_URL points a dev build at a local server, e.g. your PC's LAN IP.
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://sma3ni-api.onrender.com';

const TOKEN_KEY = 'install_token';

const secureTokenStore: TokenStore = {
  get: () => SecureStore.getItemAsync(TOKEN_KEY),
  set: (token) => SecureStore.setItemAsync(TOKEN_KEY, token),
};

export const api = createApi({ baseUrl: API_URL, tokenStore: secureTokenStore });
