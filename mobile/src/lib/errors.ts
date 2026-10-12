import { ApiError } from '@/api';
import type { MessageKey } from '@/i18n';

/** What to tell the user; the server's English messages are never shown. */
export function errorMessageKey(error: unknown): MessageKey {
  if (!(error instanceof ApiError)) {
    return 'errorGeneric';
  }
  switch (error.code) {
    case 'offline':
      return 'errorOffline';
    case 'busy':
    case 'model_loading':
      return 'errorBusy';
    case 'audio_too_long':
      return 'errorTooLong';
    case 'audio_too_large':
      return 'errorTooLarge';
    case 'invalid_audio':
    case 'unsupported_format':
      return 'errorFormat';
    case 'rate_limited':
      return 'errorRateLimited';
    default:
      return 'errorGeneric';
  }
}
