import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';

import { api } from '@/api';
import { t } from '@/i18n';
import { useColors } from '@/theme/colors';

export default function RootLayout() {
  const colors = useColors();
  // The API client retries what docs/API.md says to retry; react-query must not add more.
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { mutations: { retry: false } } }),
  );

  useEffect(() => {
    // Render's free tier sleeps after 15 min: wake it while the user picks a note.
    api.wake();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Stack
        screenOptions={{
          title: t('appName'),
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="transcript/[id]" options={{ title: t('transcriptTitle') }} />
      </Stack>
      <StatusBar style="auto" />
    </QueryClientProvider>
  );
}
