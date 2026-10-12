// Mirrors docs/API.md (v1). Fields the server adds later are ignored.

export type Script = 'arabic' | 'arabizi';

export type ServerErrorCode =
  | 'invalid_request'
  | 'invalid_audio'
  | 'unsupported_format'
  | 'unauthorized'
  | 'audio_too_large'
  | 'audio_too_long'
  | 'rate_limited'
  | 'internal_error'
  | 'model_loading'
  | 'busy';

export interface Segment {
  start: number;
  end: number;
  text: string;
}

export interface TranscribeResponse {
  request_id: string;
  text: string;
  script: Script;
  language: string;
  duration_s: number;
  segments: Segment[];
  summary: string | null;
  translation: string | null;
  replies: string[] | null;
  model_version: string;
  processing_ms: number;
}

/** A local audio file, e.g. from the document picker or the share sheet. */
export interface AudioFile {
  uri: string;
  name: string;
  mimeType: string;
}
