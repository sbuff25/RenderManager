/**
 * Persisted settings hook — stores server URL + token in AsyncStorage
 */

import { useEffect, useState, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiClient } from '../api/client';

const KEY_SERVER = '@wain_server_url';
const KEY_TOKEN = '@wain_api_token';

export interface WainSettings {
  serverUrl: string;
  apiToken: string;
}

export function useSettings() {
  const [settings, setSettings] = useState<WainSettings>({
    serverUrl: '',
    apiToken: '',
  });
  const [loaded, setLoaded] = useState(false);

  // Load on mount
  useEffect(() => {
    (async () => {
      try {
        const [url, token] = await Promise.all([
          AsyncStorage.getItem(KEY_SERVER),
          AsyncStorage.getItem(KEY_TOKEN),
        ]);
        const s: WainSettings = {
          serverUrl: url || '',
          apiToken: token || '',
        };
        setSettings(s);
        apiClient.setServer(s.serverUrl);
        apiClient.setToken(s.apiToken);
      } catch {
        // ignore
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const save = useCallback(async (newSettings: WainSettings) => {
    setSettings(newSettings);
    apiClient.setServer(newSettings.serverUrl);
    apiClient.setToken(newSettings.apiToken);
    await AsyncStorage.multiSet([
      [KEY_SERVER, newSettings.serverUrl],
      [KEY_TOKEN, newSettings.apiToken],
    ]);
  }, []);

  return { settings, save, loaded };
}
