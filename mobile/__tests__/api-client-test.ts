import { ApiError, createApi, type TokenStore } from '@/api/client';
import type { AudioFile, TranscribeResponse } from '@/api/types';

const NOTE: AudioFile = {
  uri: 'file:///cache/note.opus',
  name: 'note.opus',
  mimeType: 'audio/ogg',
};
const TRANSCRIPT: TranscribeResponse = {
  request_id: 'req_1',
  text: 'عسلامة',
  script: 'arabic',
  language: 'aeb',
  duration_s: 2,
  segments: [{ start: 0, end: 2, text: 'عسلامة' }],
  summary: null,
  translation: null,
  replies: null,
  model_version: 'test',
  processing_ms: 900,
};

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
const apiError = (status: number, code: string, headers: Record<string, string> = {}) =>
  json(status, { error: { code, message: 'server text' } }, headers);

function setup(responses: (Response | Error)[], storedToken: string | null = 'tok-1') {
  const store: TokenStore & { token: string | null } = {
    token: storedToken,
    get: async () => store.token,
    set: async (token) => {
      store.token = token;
    },
  };
  const calls: { url: string; init?: RequestInit }[] = [];
  const fetchFn = jest.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const next = responses.shift();
    if (!next) throw new Error('unexpected request');
    if (next instanceof Error) throw next;
    return next;
  }) as unknown as typeof fetch;
  const waits: number[] = [];
  const api = createApi({
    baseUrl: 'https://api.test',
    tokenStore: store,
    fetchFn,
    wait: async (seconds) => {
      waits.push(seconds);
    },
  });
  return { api, store, calls, waits };
}

const authOf = (init?: RequestInit) => (init?.headers as Record<string, string>).Authorization;

test('sends the note with the stored token', async () => {
  const { api, calls } = setup([json(200, TRANSCRIPT)]);

  await expect(api.transcribe(NOTE, 'arabic')).resolves.toEqual(TRANSCRIPT);

  expect(calls).toHaveLength(1);
  expect(calls[0]?.url).toBe('https://api.test/v1/transcribe');
  expect(authOf(calls[0]?.init)).toBe('Bearer tok-1');
  expect(calls[0]?.init?.body).toBeInstanceOf(FormData);
});

test('installs first when there is no token yet', async () => {
  const { api, store, calls } = setup([json(200, { token: 'fresh' }), json(200, TRANSCRIPT)], null);

  await api.transcribe(NOTE, 'arabic');

  expect(calls.map((c) => c.url)).toEqual([
    'https://api.test/v1/install',
    'https://api.test/v1/transcribe',
  ]);
  expect(store.token).toBe('fresh');
});

test('re-installs once on 401, as docs/API.md asks', async () => {
  const { api, store, calls } = setup([
    apiError(401, 'unauthorized'),
    json(200, { token: 'rotated' }),
    json(200, TRANSCRIPT),
  ]);

  await api.transcribe(NOTE, 'arabic');

  expect(store.token).toBe('rotated');
  expect(authOf(calls[2]?.init)).toBe('Bearer rotated');
});

test('a second 401 is not retried forever', async () => {
  const { api } = setup([
    apiError(401, 'unauthorized'),
    json(200, { token: 'rotated' }),
    apiError(401, 'unauthorized'),
  ]);

  await expect(api.transcribe(NOTE, 'arabic')).rejects.toMatchObject({ code: 'unauthorized' });
});

test('retries busy twice, honouring Retry-After', async () => {
  const { api, waits } = setup([
    apiError(503, 'busy', { 'Retry-After': '3' }),
    apiError(503, 'busy'),
    json(200, TRANSCRIPT),
  ]);

  await expect(api.transcribe(NOTE, 'arabic')).resolves.toEqual(TRANSCRIPT);
  expect(waits).toEqual([3, 4]);
});

test('gives up after two busy retries', async () => {
  const { api } = setup([apiError(503, 'busy'), apiError(503, 'busy'), apiError(503, 'busy')]);

  await expect(api.transcribe(NOTE, 'arabic')).rejects.toMatchObject({ code: 'busy' });
});

test('a long Retry-After is capped', async () => {
  const { api, waits } = setup([
    apiError(503, 'busy', { 'Retry-After': '600' }),
    json(200, TRANSCRIPT),
  ]);

  await api.transcribe(NOTE, 'arabic');
  expect(waits).toEqual([10]);
});

test('a network failure is "offline"', async () => {
  const { api } = setup([new TypeError('Network request failed')]);

  await expect(api.transcribe(NOTE, 'arabic')).rejects.toMatchObject({ code: 'offline' });
});

test('contract errors keep their code; anything else is "unknown"', async () => {
  const tooLong = setup([apiError(413, 'audio_too_long')]);
  await expect(tooLong.api.transcribe(NOTE, 'arabic')).rejects.toEqual(
    new ApiError('audio_too_long', 413),
  );

  const proxyPage = setup([new Response('<html>Bad gateway</html>', { status: 502 })]);
  await expect(proxyPage.api.transcribe(NOTE, 'arabic')).rejects.toMatchObject({
    code: 'unknown',
    status: 502,
  });
});

test('wake() pings health and never throws', async () => {
  const { api, calls } = setup([new TypeError('offline')]);

  api.wake();
  await new Promise((resolve) => setTimeout(resolve, 0));

  expect(calls[0]?.url).toBe('https://api.test/v1/health');
});
