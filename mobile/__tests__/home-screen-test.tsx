import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { ApiError, api } from '@/api';
import HomeScreen from '@/app/index';
import { t } from '@/i18n';
import { deleteCachedAudio, pickAudio } from '@/lib/pick';
import { getTranscript } from '@/lib/transcripts';

jest.mock('expo-router', () => ({ router: { push: jest.fn() } }));
jest.mock('@/lib/pick', () => ({ pickAudio: jest.fn(), deleteCachedAudio: jest.fn() }));
jest.mock('@/api', () => {
  const actual = jest.requireActual('@/api/client');
  return { ApiError: actual.ApiError, api: { transcribe: jest.fn(), wake: jest.fn() } };
});

const NOTE = { uri: 'file:///cache/note.opus', name: 'note.opus', mimeType: 'audio/ogg' };

async function renderHome() {
  // gcTime: Infinity starts no cache timer, so Jest can exit as soon as the tests end.
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false, gcTime: Infinity } },
  });
  await render(
    <QueryClientProvider client={client}>
      <HomeScreen />
    </QueryClientProvider>,
  );
}

beforeEach(() => jest.clearAllMocks());

test('shows how to share a voice note and the privacy promise', async () => {
  await renderHome();

  expect(screen.getByText(t('howToTitle'))).toBeTruthy();
  expect(screen.getByText(t('howToStep2'))).toBeTruthy();
  expect(screen.getByText(t('privacy'))).toBeTruthy();
});

test('a picked note is transcribed, its cached copy deleted, and the transcript opened', async () => {
  jest.mocked(pickAudio).mockResolvedValue(NOTE);
  jest.mocked(api.transcribe).mockResolvedValue({
    request_id: 'req_42',
    text: 'عسلامة',
  } as Awaited<ReturnType<typeof api.transcribe>>);
  await renderHome();

  await fireEvent.press(screen.getByText(t('pickAudio')));

  await screen.findByText(t('pickAudio'));
  expect(api.transcribe).toHaveBeenCalledWith(NOTE, 'arabic');
  expect(deleteCachedAudio).toHaveBeenCalledWith(NOTE);
  expect(getTranscript('req_42')?.text).toBe('عسلامة');
  expect(router.push).toHaveBeenCalledWith({
    pathname: '/transcript/[id]',
    params: { id: 'req_42' },
  });
});

test('a failure is explained in the user language, and the copy is still deleted', async () => {
  jest.mocked(pickAudio).mockResolvedValue(NOTE);
  jest.mocked(api.transcribe).mockRejectedValue(new ApiError('audio_too_long', 413));
  await renderHome();

  await fireEvent.press(screen.getByText(t('pickAudio')));

  expect(await screen.findByText(t('errorTooLong'))).toBeTruthy();
  expect(deleteCachedAudio).toHaveBeenCalledWith(NOTE);
  expect(router.push).not.toHaveBeenCalled();
});

test('cancelling the picker sends nothing', async () => {
  jest.mocked(pickAudio).mockResolvedValue(null);
  await renderHome();

  await fireEvent.press(screen.getByText(t('pickAudio')));

  await screen.findByText(t('pickAudio'));
  expect(api.transcribe).not.toHaveBeenCalled();
});
