import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';

import type { AudioFile } from '@/api';

/** Let the user choose one audio file; null if they cancel. */
export async function pickAudio(): Promise<AudioFile | null> {
  const result = await DocumentPicker.getDocumentAsync({
    // WhatsApp notes are .opus (audio/ogg); some file managers label them application/ogg.
    type: ['audio/*', 'application/ogg'],
    copyToCacheDirectory: true,
  });
  const asset = result.canceled ? undefined : result.assets[0];
  if (!asset) {
    return null;
  }
  return {
    uri: asset.uri,
    name: asset.name,
    mimeType: asset.mimeType ?? 'application/octet-stream',
  };
}

/** Remove the app's cached copy of a voice note (mobile/AGENTS.md). */
export function deleteCachedAudio(audio: AudioFile): void {
  try {
    const file = new File(audio.uri);
    if (file.exists) {
      file.delete();
    }
  } catch {
    // Not a file we own (e.g. a content:// URI): nothing cached to delete.
  }
}
