import { useMutation } from '@tanstack/react-query';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { api } from '@/api';
import { type MessageKey, t } from '@/i18n';
import { errorMessageKey } from '@/lib/errors';
import { deleteCachedAudio, pickAudio } from '@/lib/pick';
import { saveTranscript } from '@/lib/transcripts';
import { useColors } from '@/theme/colors';

const STEPS: MessageKey[] = ['howToStep1', 'howToStep2', 'howToStep3'];

export default function HomeScreen() {
  const colors = useColors();
  const transcription = useMutation({
    mutationFn: async () => {
      const audio = await pickAudio();
      if (!audio) {
        return null;
      }
      try {
        return await api.transcribe(audio, 'arabic');
      } finally {
        // Success or not, the app keeps no copy of the voice note.
        deleteCachedAudio(audio);
      }
    },
    onSuccess: (transcript) => {
      if (transcript) {
        saveTranscript(transcript);
        router.push({ pathname: '/transcript/[id]', params: { id: transcript.request_id } });
      }
    },
  });

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={[styles.tagline, { color: colors.text }]}>{t('tagline')}</Text>

      <Pressable
        accessibilityRole="button"
        disabled={transcription.isPending}
        onPress={() => transcription.mutate()}
        style={({ pressed }) => [
          styles.button,
          { backgroundColor: colors.accent, opacity: pressed || transcription.isPending ? 0.7 : 1 },
        ]}
      >
        {transcription.isPending ? (
          <View style={styles.busy}>
            <ActivityIndicator color="#FFFFFF" />
            <Text style={styles.buttonText}>{t('transcribing')}</Text>
          </View>
        ) : (
          <Text style={styles.buttonText}>{t('pickAudio')}</Text>
        )}
      </Pressable>
      {transcription.isError ? (
        <Text accessibilityRole="alert" style={[styles.error, { color: colors.accent }]}>
          {t(errorMessageKey(transcription.error))}
        </Text>
      ) : null}

      <Text style={[styles.heading, { color: colors.text }]} accessibilityRole="header">
        {t('howToTitle')}
      </Text>
      {STEPS.map((step, index) => (
        <View key={step} style={styles.step}>
          <Text style={[styles.stepNumber, { color: colors.accent }]}>{index + 1}</Text>
          <Text style={[styles.stepText, { color: colors.text }]}>{t(step)}</Text>
        </View>
      ))}

      <Text style={[styles.privacy, { color: colors.muted }]}>{t('privacy')}</Text>
    </ScrollView>
  );
}

// Layout uses start/end and the default text alignment, so Arabic mirrors itself.
const styles = StyleSheet.create({
  container: { padding: 24, gap: 16 },
  tagline: { fontSize: 22, fontWeight: '600' },
  button: { borderRadius: 12, paddingVertical: 16, paddingHorizontal: 20, alignItems: 'center' },
  busy: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  buttonText: { color: '#FFFFFF', fontSize: 17, fontWeight: '600' },
  error: { fontSize: 15 },
  heading: { fontSize: 18, fontWeight: '600', marginTop: 8 },
  step: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  stepNumber: { fontSize: 18, fontWeight: '700', minWidth: 20 },
  stepText: { fontSize: 16, flex: 1 },
  privacy: { fontSize: 14, marginTop: 16 },
});
