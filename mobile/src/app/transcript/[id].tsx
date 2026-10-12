import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native';

import { t } from '@/i18n';
import { getTranscript } from '@/lib/transcripts';
import { useColors } from '@/theme/colors';

export default function TranscriptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const transcript = getTranscript(id);
  const colors = useColors();
  const [copied, setCopied] = useState(false);

  if (!transcript) {
    return (
      <View style={styles.container}>
        <Text style={{ color: colors.text }}>{t('transcriptMissing')}</Text>
      </View>
    );
  }

  const copy = async () => {
    await Clipboard.setStringAsync(transcript.text);
    setCopied(true);
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={[styles.meta, { color: colors.muted }]}>
        {t('durationSeconds').replace('{seconds}', String(Math.round(transcript.duration_s)))}
      </Text>
      <Text
        selectable
        style={[
          styles.text,
          { color: colors.text },
          // The content's own direction, whatever the app language: Arabic reads right to left.
          { textAlign: transcript.script === 'arabic' ? 'right' : 'left' },
        ]}
      >
        {transcript.text || t('transcriptEmpty')}
      </Text>
      <View style={styles.actions}>
        <Pressable
          accessibilityRole="button"
          onPress={copy}
          style={[styles.button, { backgroundColor: colors.accent }]}
        >
          <Text style={styles.buttonText}>{copied ? t('copied') : t('copy')}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={() => Share.share({ message: transcript.text })}
          style={[styles.button, styles.secondary, { borderColor: colors.accent }]}
        >
          <Text style={[styles.buttonText, { color: colors.accent }]}>{t('share')}</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, gap: 16 },
  meta: { fontSize: 14 },
  text: { fontSize: 20, lineHeight: 32 },
  actions: { flexDirection: 'row', gap: 12 },
  button: { flex: 1, borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  secondary: { backgroundColor: 'transparent', borderWidth: 2 },
  buttonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
});
