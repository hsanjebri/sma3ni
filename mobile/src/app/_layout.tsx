import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { t } from '@/i18n';
import { useColors } from '@/theme/colors';

export default function RootLayout() {
  const colors = useColors();
  return (
    <>
      <Stack
        screenOptions={{
          title: t('appName'),
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
          contentStyle: { backgroundColor: colors.background },
        }}
      />
      <StatusBar style="auto" />
    </>
  );
}
