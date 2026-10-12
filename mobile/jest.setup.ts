// Looping animations would keep Jest running after the tests: every test runs
// as if the phone asked for reduced motion, which the app supports anyway.
jest.mock('@/lib/motion', () => ({ useReducedMotion: () => true }));
