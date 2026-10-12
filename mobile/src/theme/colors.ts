import { useColorScheme } from 'react-native';

const light = { background: '#FFFFFF', text: '#11181C', muted: '#5F6B73', accent: '#C8102E' };
const dark: typeof light = {
  background: '#101415',
  text: '#ECEDEE',
  muted: '#9BA1A6',
  accent: '#FF5A6E',
};

export type Colors = typeof light;

export function useColors(): Colors {
  return useColorScheme() === 'dark' ? dark : light;
}
