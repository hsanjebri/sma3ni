import * as SecureStore from 'expo-secure-store';
import { useEffect, useState } from 'react';

const KEY = 'onboarded';

export async function markOnboarded(): Promise<void> {
  await SecureStore.setItemAsync(KEY, '1');
}

/** Whether onboarding was seen: undefined while reading, then true or false. */
export function useOnboarded(): boolean | undefined {
  const [onboarded, setOnboarded] = useState<boolean>();

  useEffect(() => {
    SecureStore.getItemAsync(KEY)
      .then((value) => setOnboarded(value === '1'))
      // Unreadable storage must not lock the user out of the app.
      .catch(() => setOnboarded(true));
  }, []);

  return onboarded;
}
