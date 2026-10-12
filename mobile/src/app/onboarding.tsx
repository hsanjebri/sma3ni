import { Ionicons } from '@react-native-vector-icons/ionicons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Animated, I18nManager, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/Button';
import { FadeIn } from '@/components/FadeIn';
import { Waveform } from '@/components/Waveform';
import { type MessageKey, t } from '@/i18n';
import { useReducedMotion } from '@/lib/motion';
import { markOnboarded } from '@/lib/onboarding';
import { type Colors, useColors } from '@/theme/colors';

const SLIDES: {
  title: MessageKey;
  body: MessageKey;
  Art: (props: { colors: Colors }) => React.JSX.Element;
}[] = [
  { title: 'onboarding1Title', body: 'onboarding1Body', Art: VoiceToText },
  { title: 'onboarding2Title', body: 'onboarding2Body', Art: ShareFromWhatsApp },
  { title: 'onboarding3Title', body: 'onboarding3Body', Art: Private },
];

export default function OnboardingScreen() {
  const colors = useColors();
  const [index, setIndex] = useState(0);
  const slide = SLIDES[index] ?? SLIDES[0]!;
  const last = index === SLIDES.length - 1;

  const finish = async () => {
    await markOnboarded().catch(() => undefined);
    router.replace('/');
  };

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]}>
      <View style={styles.top}>
        {last ? null : (
          <Pressable accessibilityRole="button" onPress={finish} hitSlop={12}>
            <Text style={[styles.skip, { color: colors.muted }]}>{t('skip')}</Text>
          </Pressable>
        )}
      </View>

      {/* key: each slide mounts fresh, so its art and text animate in again. */}
      <View key={index} style={styles.body}>
        <FadeIn style={styles.art}>
          <slide.Art colors={colors} />
        </FadeIn>
        <FadeIn delay={120}>
          <Text style={[styles.title, { color: colors.text }]} accessibilityRole="header">
            {t(slide.title)}
          </Text>
        </FadeIn>
        <FadeIn delay={220}>
          <Text style={[styles.text, { color: colors.muted }]}>{t(slide.body)}</Text>
        </FadeIn>
      </View>

      <View style={styles.bottom}>
        <View style={styles.dots} accessibilityLabel={`${index + 1} / ${SLIDES.length}`}>
          {SLIDES.map((_, dot) => (
            <View
              key={dot}
              style={[
                styles.dot,
                { backgroundColor: dot === index ? colors.accent : colors.border },
                dot === index && styles.dotActive,
              ]}
            />
          ))}
        </View>
        <Button
          label={last ? t('start') : t('next')}
          icon={last ? 'checkmark' : I18nManager.isRTL ? 'arrow-back' : 'arrow-forward'}
          onPress={last ? finish : () => setIndex(index + 1)}
        />
      </View>
    </SafeAreaView>
  );
}

/** A voice note turning into lines of text. */
function VoiceToText({ colors }: { colors: Colors }) {
  return (
    <View style={[styles.card, { backgroundColor: colors.surface }]}>
      <Waveform color={colors.accent} active />
      <Ionicons name="arrow-down" size={22} color={colors.muted} />
      {[1, 0.8, 0.55].map((width, line) => (
        <FadeIn key={line} delay={300 + line * 180}>
          <View
            style={[styles.textLine, { width: `${width * 100}%`, backgroundColor: colors.border }]}
          />
        </FadeIn>
      ))}
    </View>
  );
}

/** A WhatsApp-style voice note, shared to Sma3ni. */
function ShareFromWhatsApp({ colors }: { colors: Colors }) {
  const nudge = usePulse();
  const translateX = nudge.interpolate({
    inputRange: [0, 1],
    outputRange: [0, I18nManager.isRTL ? -8 : 8],
  });
  return (
    <View style={[styles.card, { backgroundColor: colors.surface }]}>
      <View style={[styles.bubble, { backgroundColor: colors.accentSoft }]}>
        <Ionicons name="play" size={20} color={colors.accent} />
        <Waveform color={colors.accent} bars={12} height={26} />
        <Text style={[styles.bubbleTime, { color: colors.muted }]}>0:42</Text>
      </View>
      <View style={styles.shareRow}>
        <View style={[styles.pill, { borderColor: colors.border }]}>
          <Ionicons name="share-social-outline" size={18} color={colors.text} />
          <Text style={{ color: colors.text }}>{t('shareAction')}</Text>
        </View>
        <Animated.View style={{ transform: [{ translateX }] }}>
          <Ionicons
            name={I18nManager.isRTL ? 'arrow-back' : 'arrow-forward'}
            size={22}
            color={colors.accent}
          />
        </Animated.View>
        <View style={[styles.appBadge, { backgroundColor: colors.accent }]}>
          <Ionicons name="mic" size={18} color={colors.onAccent} />
          <Text style={[styles.appBadgeText, { color: colors.onAccent }]}>{t('appName')}</Text>
        </View>
      </View>
    </View>
  );
}

/** A lock with a soft pulse: nothing kept, nothing shared. */
function Private({ colors }: { colors: Colors }) {
  const pulse = usePulse();
  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.25] });
  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.5, 0] });
  return (
    <View style={[styles.card, styles.center, { backgroundColor: colors.surface }]}>
      <Animated.View
        style={[styles.ring, { borderColor: colors.accent, opacity, transform: [{ scale }] }]}
      />
      <View style={[styles.lock, { backgroundColor: colors.accentSoft }]}>
        <Ionicons name="lock-closed" size={44} color={colors.accent} />
      </View>
    </View>
  );
}

function usePulse(): Animated.Value {
  const reduced = useReducedMotion();
  const [value] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(value, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(value, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [reduced, value]);
  return value;
}

const styles = StyleSheet.create({
  screen: { flex: 1, paddingHorizontal: 24 },
  top: { height: 44, alignItems: 'flex-end', justifyContent: 'center' },
  skip: { fontSize: 16, fontWeight: '600' },
  body: { flex: 1, justifyContent: 'center', gap: 20 },
  art: { alignItems: 'stretch' },
  title: { fontSize: 28, fontWeight: '800' },
  text: { fontSize: 17, lineHeight: 25 },
  bottom: { gap: 20, paddingBottom: 16 },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotActive: { width: 24 },
  card: { borderRadius: 24, padding: 24, gap: 14, alignItems: 'center', minHeight: 220 },
  center: { justifyContent: 'center' },
  textLine: { height: 12, borderRadius: 6, alignSelf: 'flex-start' },
  bubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 18,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignSelf: 'stretch',
  },
  bubbleTime: { fontSize: 12 },
  shareRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 10 },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  appBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  appBadgeText: { fontWeight: '700' },
  ring: { position: 'absolute', width: 132, height: 132, borderRadius: 66, borderWidth: 3 },
  lock: {
    width: 104,
    height: 104,
    borderRadius: 52,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
