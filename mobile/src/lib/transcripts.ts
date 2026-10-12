import type { TranscribeResponse } from '@/api';

// In memory until the history step stores transcripts in SQLite on the phone
// (docs/MOBILE.md). Never sent anywhere else.
const transcripts = new Map<string, TranscribeResponse>();

export function saveTranscript(transcript: TranscribeResponse): void {
  transcripts.set(transcript.request_id, transcript);
}

export function getTranscript(id: string): TranscribeResponse | undefined {
  return transcripts.get(id);
}
