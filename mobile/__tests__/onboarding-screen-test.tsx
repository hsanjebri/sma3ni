import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import OnboardingScreen from '@/app/onboarding';
import { t } from '@/i18n';
import { markOnboarded } from '@/lib/onboarding';

jest.mock('expo-router', () => ({ router: { replace: jest.fn() } }));
jest.mock('@/lib/onboarding', () => ({ markOnboarded: jest.fn(async () => undefined) }));

beforeEach(() => jest.clearAllMocks());

test('three slides, then the app; seen only once', async () => {
  await render(<OnboardingScreen />);
  expect(screen.getByText(t('onboarding1Title'))).toBeTruthy();

  await fireEvent.press(screen.getByText(t('next')));
  expect(screen.getByText(t('onboarding2Title'))).toBeTruthy();

  await fireEvent.press(screen.getByText(t('next')));
  expect(screen.getByText(t('onboarding3Title'))).toBeTruthy();
  expect(screen.queryByText(t('skip'))).toBeNull();

  await fireEvent.press(screen.getByText(t('start')));
  expect(markOnboarded).toHaveBeenCalled();
  expect(router.replace).toHaveBeenCalledWith('/');
});

test('skip goes straight to the app', async () => {
  await render(<OnboardingScreen />);

  await fireEvent.press(screen.getByText(t('skip')));

  expect(markOnboarded).toHaveBeenCalled();
  expect(router.replace).toHaveBeenCalledWith('/');
});
