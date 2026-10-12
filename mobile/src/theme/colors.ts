import { useColorScheme } from 'react-native';

// Tunisian red as the accent; everything else stays quiet so the transcript leads.
const light = {
  background: '#F6F4F2',
  surface: '#FFFFFF',
  text: '#16181A',
  muted: '#646B72',
  border: '#E6E1DC',
  accent: '#E70013',
  accentSoft: '#FDE7E9',
  onAccent: '#FFFFFF',
};

const dark: typeof light = {
  background: '#0E1112',
  surface: '#181C1E',
  text: '#ECEDEE',
  muted: '#9BA1A6',
  border: '#2A3033',
  accent: '#FF4D5E',
  accentSoft: '#3A1A1E',
  onAccent: '#FFFFFF',
};

export type Colors = typeof light;

export function useColors(): Colors {
  return useColorScheme() === 'dark' ? dark : light;
}
