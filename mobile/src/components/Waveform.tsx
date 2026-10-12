import { useEffect, useMemo } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';

import { useReducedMotion } from '@/lib/motion';

interface Props {
  color: string;
  /** Faster and taller while something is being transcribed. */
  active?: boolean;
  bars?: number;
  height?: number;
}

// A fixed, voice-like profile: the bars rest at these heights and pulse around them.
const PROFILE = [0.35, 0.6, 0.9, 0.55, 1, 0.7, 0.4, 0.8, 0.5, 0.95, 0.6, 0.3, 0.75, 0.45, 0.65];

export function Waveform({ color, active = false, bars = 15, height = 56 }: Props) {
  const reduced = useReducedMotion();
  const values = useMemo(() => Array.from({ length: bars }, () => new Animated.Value(0)), [bars]);

  useEffect(() => {
    if (reduced) return;
    const period = active ? 380 : 900;
    const loops = values.map((value, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay((index * period) / bars),
          Animated.timing(value, {
            toValue: 1,
            duration: period,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(value, {
            toValue: 0,
            duration: period,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
      ),
    );
    loops.forEach((loop) => loop.start());
    return () => loops.forEach((loop) => loop.stop());
  }, [active, bars, reduced, values]);

  const swing = active ? 0.55 : 0.3;
  return (
    <View style={[styles.row, { height }]} accessible={false} importantForAccessibility="no">
      {values.map((value, index) => {
        const rest = PROFILE[index % PROFILE.length] ?? 0.5;
        const scaleY = value.interpolate({
          inputRange: [0, 1],
          outputRange: [rest * (1 - swing), Math.min(1, rest + swing * 0.6)],
        });
        return (
          <Animated.View
            key={index}
            style={[
              styles.bar,
              { height, backgroundColor: color, transform: [{ scaleY: reduced ? rest : scaleY }] },
            ]}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5 },
  bar: { width: 6, borderRadius: 3 },
});
