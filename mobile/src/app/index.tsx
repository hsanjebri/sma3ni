import { Ionicons } from '@react-native-vector-icons/ionicons';
import { useMutation } from '@tanstack/react-query';
import { Redirect, router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '@/api';
import { Button } from '@/components/Button';
import { FadeIn } from '@/components/FadeIn';
import { Waveform } from '@/components/Waveform';
import { type MessageKey, t } from '@/i18n';
import { errorMessageKey } from '@/lib/errors';
import { useOnboarded } from '@/lib/onboarding';
import { deleteCachedAudio, pickAudio } from '@/lib/pick';
import { saveTranscript } from '@/lib/transcripts';
import { useColors } from '@/theme/colors';

const STEPS: MessageKey[] = ['howToStep1', 'howToStep2', 'howToStep3'];
// Render's free tier takes ~20 s to wake: after this long, say so.
const WAKING_UP_AFTER_S = 5;

export default function HomeScreen() {
  const colors = useColors();
  const onboarded = useOnboarded();
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
  const waited = useSecondsWhile(transcription.isPending);

  if (onboarded === undefined) {
    return null;
  }
  if (!onboarded) {
    return <Redirect href="/onboarding" />;
  }

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <FadeIn style={styles.hero}>
          <Text style={[styles.appName, { color: colors.accent }]}>{t('appName')}</Text>
          <Text style={[styles.tagline, { color: colors.text }]}>{t('tagline')}</Text>
          <Waveform color={colors.accent} active={transcription.isPending} />
        </FadeIn>

        <FadeIn delay={100} style={[styles.card, { backgroundColor: colors.surface }]}>
          {transcription.isPending ? (
            <View style={styles.pending} accessibilityLiveRegion="polite">
              <Text style={[styles.cardTitle, { color: colors.text }]}>{t('transcribing')}</Text>
              <Text style={[styles.cardText, { color: colors.muted }]}>
                {waited >= WAKING_UP_AFTER_S ? t('wakingUp') : t('usuallyFast')}
              </Text>
            </View>
          ) : (
            <>
              <CardHeader icon="document-attach-outline" title={t('pickTitle')} />
              <Text style={[styles.cardText, { color: colors.muted }]}>{t('pickBody')}</Text>
              <Button label={t('pickAudio')} icon="mic" onPress={() => transcription.mutate()} />
            </>
          )}
          {transcription.isError ? (
            <View
              accessibilityRole="alert"
              style={[styles.error, { backgroundColor: colors.accentSoft }]}
            >
              <Ionicons name="alert-circle" size={20} color={colors.accent} />
              <Text style={[styles.errorText, { color: colors.text }]}>
                {t(errorMessageKey(transcription.error))}
              </Text>
            </View>
          ) : null}
        </FadeIn>

        <FadeIn delay={200} style={[styles.card, { backgroundColor: colors.surface }]}>
          <CardHeader icon="logo-whatsapp" title={t('howToTitle')} />
          {STEPS.map((step, index) => (
            <View key={step} style={styles.step}>
              <View style={[styles.stepNumber, { backgroundColor: colors.accentSoft }]}>
                <Text style={[styles.stepNumberText, { color: colors.accent }]}>{index + 1}</Text>
              </View>
              <Text style={[styles.stepText, { color: colors.text }]}>{t(step)}</Text>
            </View>
          ))}
          <Button
            label={t('openWhatsApp')}
            icon="open-outline"
            variant="secondary"
            onPress={() => Linking.openURL('whatsapp://').catch(() => undefined)}
          />
        </FadeIn>

        <FadeIn delay={300} style={styles.privacy}>
          <Ionicons name="lock-closed" size={16} color={colors.muted} />
          <Text style={[styles.privacyText, { color: colors.muted }]}>{t('privacy')}</Text>
        </FadeIn>
      </ScrollView>
    </SafeAreaView>
  );
}

function CardHeader({
  icon,
  title,
}: {
  icon: 'document-attach-outline' | 'logo-whatsapp';
  title: string;
}) {
  const colors = useColors();
  return (
    <View style={styles.cardHeader}>
      <View style={[styles.cardIcon, { backgroundColor: colors.accentSoft }]}>
        <Ionicons name={icon} size={22} color={colors.accent} />
      </View>
      <Text style={[styles.cardTitle, { color: colors.text }]} accessibilityRole="header">
        {title}
      </Text>
    </View>
  );
}

/** Whole seconds since `running` became true; 0 otherwise. */
function useSecondsWhile(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => {
      clearInterval(timer);
      setSeconds(0);
    };
  }, [running]);
  return running ? seconds : 0;
}

// Layout uses start/end and default text alignment, so Arabic mirrors itself.
const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 20, gap: 16, paddingBottom: 40 },
  hero: { gap: 10, paddingVertical: 12 },
  appName: { fontSize: 34, fontWeight: '800' },
  tagline: { fontSize: 20, fontWeight: '600', lineHeight: 28 },
  card: { borderRadius: 20, padding: 18, gap: 14 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  cardIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: { fontSize: 18, fontWeight: '700', flexShrink: 1 },
  cardText: { fontSize: 15, lineHeight: 22 },
  pending: { gap: 6, paddingVertical: 8 },
  error: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, padding: 12 },
  errorText: { fontSize: 15, flex: 1 },
  step: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumberText: { fontWeight: '800' },
  stepText: { fontSize: 15, flex: 1 },
  privacy: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingHorizontal: 4 },
  privacyText: { fontSize: 13, lineHeight: 19, flex: 1 },
});
