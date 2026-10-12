import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { type MessageKey, t } from '@/i18n';
import { useColors } from '@/theme/colors';

const STEPS: MessageKey[] = ['howToStep1', 'howToStep2', 'howToStep3'];

export default function HomeScreen() {
  const colors = useColors();
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={[styles.tagline, { color: colors.text }]}>{t('tagline')}</Text>

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
  heading: { fontSize: 18, fontWeight: '600', marginTop: 8 },
  step: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  stepNumber: { fontSize: 18, fontWeight: '700', minWidth: 20 },
  stepText: { fontSize: 16, flex: 1 },
  privacy: { fontSize: 14, marginTop: 16 },
});
