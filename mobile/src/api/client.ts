import type { AudioFile, Script, ServerErrorCode, TranscribeResponse } from './types';

const SERVER_CODES: readonly ServerErrorCode[] = [
  'invalid_request',
  'invalid_audio',
  'unsupported_format',
  'unauthorized',
  'audio_too_large',
  'audio_too_long',
  'rate_limited',
  'internal_error',
  'model_loading',
  'busy',
];
// docs/API.md: the client retries `busy` / `model_loading` with backoff.
const MAX_BUSY_RETRIES = 2;
const MAX_WAIT_S = 10;

export type ApiErrorCode = ServerErrorCode | 'offline' | 'unknown';

export class ApiError extends Error {
  constructor(
    readonly code: ApiErrorCode,
    readonly status: number,
    readonly retryAfterS?: number,
  ) {
    super(code);
    this.name = 'ApiError';
  }
}

export interface TokenStore {
  get(): Promise<string | null>;
  set(token: string): Promise<void>;
}

export interface ApiOptions {
  baseUrl: string;
  tokenStore: TokenStore;
  fetchFn?: typeof fetch;
  wait?: (seconds: number) => Promise<void>;
}

export interface Api {
  transcribe(audio: AudioFile, script: Script): Promise<TranscribeResponse>;
  /** Fire-and-forget: Render's free tier sleeps, so start waking it early. */
  wake(): void;
}

const sleep = (seconds: number) => new Promise<void>((done) => setTimeout(done, seconds * 1000));

export function createApi({ baseUrl, tokenStore, fetchFn = fetch, wait = sleep }: ApiOptions): Api {
  async function request(path: string, init?: RequestInit): Promise<Response> {
    try {
      return await fetchFn(`${baseUrl}${path}`, init);
    } catch {
      throw new ApiError('offline', 0);
    }
  }

  async function toError(response: Response): Promise<ApiError> {
    let code: ApiErrorCode = 'unknown';
    try {
      const body = (await response.json()) as { error?: { code?: string } };
      const sent = body.error?.code;
      if (SERVER_CODES.includes(sent as ServerErrorCode)) {
        code = sent as ServerErrorCode;
      }
    } catch {
      // Not the API's JSON envelope (e.g. a proxy page): keep `unknown`.
    }
    const retryAfter = Number(response.headers.get('retry-after'));
    return new ApiError(code, response.status, retryAfter > 0 ? retryAfter : undefined);
  }

  async function install(): Promise<string> {
    const response = await request('/v1/install', { method: 'POST' });
    if (!response.ok) {
      throw await toError(response);
    }
    const { token } = (await response.json()) as { token: string };
    await tokenStore.set(token);
    return token;
  }

  async function transcribe(audio: AudioFile, script: Script): Promise<TranscribeResponse> {
    let token = (await tokenStore.get()) ?? (await install());
    let reinstalled = false;
    for (let busyRetries = 0; ;) {
      // A FormData body is consumed by a request, so build one per attempt.
      const body = new FormData();
      // React Native's FormData takes a file as { uri, name, type }; the DOM
      // typings only know Blob, hence the cast.
      body.append('audio', {
        uri: audio.uri,
        name: audio.name,
        type: audio.mimeType,
      } as unknown as Blob);
      body.append('script', script);

      const response = await request('/v1/transcribe', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body,
      });
      if (response.ok) {
        return (await response.json()) as TranscribeResponse;
      }

      const error = await toError(response);
      if (error.code === 'unauthorized' && !reinstalled) {
        // docs/API.md: the signing key rotated; install again, retry once.
        token = await install();
        reinstalled = true;
        continue;
      }
      if (
        (error.code === 'busy' || error.code === 'model_loading') &&
        busyRetries < MAX_BUSY_RETRIES
      ) {
        busyRetries += 1;
        await wait(Math.min(error.retryAfterS ?? 2 * busyRetries, MAX_WAIT_S));
        continue;
      }
      throw error;
    }
  }

  function wake(): void {
    request('/v1/health').catch(() => undefined);
  }

  return { transcribe, wake };
}
