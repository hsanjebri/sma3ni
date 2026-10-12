import { Ionicons } from '@react-native-vector-icons/ionicons';
import * as Haptics from 'expo-haptics';
import { type ComponentProps, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text } from 'react-native';

import { useColors } from '@/theme/colors';

interface Props {
  label: string;
  onPress: () => void;
  icon?: ComponentProps<typeof Ionicons>['name'];
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

export function Button({ label, onPress, icon, variant = 'primary', disabled = false }: Props) {
  const colors = useColors();
  const [scale] = useState(() => new Animated.Value(1));
  const primary = variant === 'primary';
  const foreground = primary ? colors.onAccent : colors.accent;

  const pressTo = (value: number) =>
    Animated.spring(scale, { toValue: value, useNativeDriver: true, speed: 40 }).start();

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled }}
        disabled={disabled}
        onPressIn={() => pressTo(0.97)}
        onPressOut={() => pressTo(1)}
        onPress={() => {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
          onPress();
        }}
        style={[
          styles.button,
          primary
            ? { backgroundColor: colors.accent }
            : { backgroundColor: colors.accentSoft, borderColor: colors.accent },
          disabled && styles.disabled,
        ]}
      >
        {icon ? <Ionicons name={icon} size={20} color={foreground} /> : null}
        <Text style={[styles.label, { color: foreground }]}>{label}</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    borderRadius: 14,
    paddingVertical: 15,
    paddingHorizontal: 20,
  },
  disabled: { opacity: 0.6 },
  label: { fontSize: 16, fontWeight: '700' },
});
