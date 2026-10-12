import { fireEvent, render, screen } from '@testing-library/react-native';
import * as Clipboard from 'expo-clipboard';

import type { TranscribeResponse } from '@/api';
import TranscriptScreen from '@/app/transcript/[id]';
import { t } from '@/i18n';
import { errorMessageKey } from '@/lib/errors';
import { saveTranscript } from '@/lib/transcripts';

jest.mock('expo-router', () => ({ useLocalSearchParams: jest.fn(() => ({ id: 'req_7' })) }));
jest.mock('expo-clipboard', () => ({ setStringAsync: jest.fn(async () => true) }));
jest.mock('@/api', () => jest.requireActual('@/api/client'));

test('shows the transcript and copies it', async () => {
  saveTranscript({
    request_id: 'req_7',
    text: 'عسلامة، توا نوصل',
    script: 'arabic',
    duration_s: 4.2,
  } as TranscribeResponse);
  await render(<TranscriptScreen />);

  expect(screen.getByText('عسلامة، توا نوصل')).toBeTruthy();
  await fireEvent.press(screen.getByText(t('copy')));

  expect(Clipboard.setStringAsync).toHaveBeenCalledWith('عسلامة، توا نوصل');
  expect(await screen.findByText(t('copied'))).toBeTruthy();
});

test('errors map to user messages', () => {
  const { ApiError } = jest.requireActual('@/api/client');
  expect(errorMessageKey(new ApiError('offline', 0))).toBe('errorOffline');
  expect(errorMessageKey(new ApiError('busy', 503))).toBe('errorBusy');
  expect(errorMessageKey(new ApiError('unsupported_format', 400))).toBe('errorFormat');
  expect(errorMessageKey(new ApiError('internal_error', 500))).toBe('errorGeneric');
  expect(errorMessageKey(new Error('boom'))).toBe('errorGeneric');
});
