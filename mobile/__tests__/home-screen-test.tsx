import { render, screen } from '@testing-library/react-native';

import HomeScreen from '@/app/index';
import { t } from '@/i18n';

describe('<HomeScreen />', () => {
  test('shows how to share a voice note and the privacy promise', async () => {
    await render(<HomeScreen />);

    expect(screen.getByText(t('howToTitle'))).toBeTruthy();
    expect(screen.getByText(t('howToStep2'))).toBeTruthy();
    expect(screen.getByText(t('privacy'))).toBeTruthy();
  });
});
