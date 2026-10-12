import { Ionicons } from '@react-native-vector-icons/ionicons';
import * as Clipboard from 'expo-clipboard';
import * as Haptics from 'expo-haptics';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, Share, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/Button';
import { FadeIn } from '@/components/FadeIn';
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
      <View style={styles.content}>
        <Text style={{ color: colors.text }}>{t('transcriptMissing')}</Text>
      </View>
    );
  }

  const copy = async () => {
    await Clipboard.setStringAsync(transcript.text);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    setCopied(true);
  };

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <FadeIn style={styles.meta}>
        <Ionicons name="mic-outline" size={16} color={colors.muted} />
        <Text style={[styles.metaText, { color: colors.muted }]}>
          {t('durationSeconds').replace('{seconds}', String(Math.round(transcript.duration_s)))}
        </Text>
      </FadeIn>

      <FadeIn delay={80} style={[styles.card, { backgroundColor: colors.surface }]}>
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
      </FadeIn>

      <FadeIn delay={160} style={styles.actions}>
        <View style={styles.action}>
          <Button
            label={copied ? t('copied') : t('copy')}
            icon={copied ? 'checkmark' : 'copy-outline'}
            onPress={copy}
          />
        </View>
        <View style={styles.action}>
          <Button
            label={t('share')}
            icon="share-social-outline"
            variant="secondary"
            onPress={() => Share.share({ message: transcript.text })}
          />
        </View>
      </FadeIn>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 16 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  metaText: { fontSize: 14 },
  card: { borderRadius: 20, padding: 20 },
  text: { fontSize: 21, lineHeight: 34 },
  actions: { flexDirection: 'row', gap: 12 },
  action: { flex: 1 },
});
