import { createContext } from 'react';
import type { WainSettings } from './hooks/useSettings';

interface SettingsContextValue {
  settings: WainSettings;
  save: (s: WainSettings) => Promise<void>;
  loaded: boolean;
}

export const SettingsContext = createContext<SettingsContextValue>({
  settings: { serverUrl: '', apiToken: '' },
  save: async () => {},
  loaded: false,
});
