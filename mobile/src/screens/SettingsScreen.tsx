import React, { useState, useContext } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '../theme/colors';
import { apiClient } from '../api/client';
import { SettingsContext } from '../SettingsContext';

export function SettingsScreen() {
  const { settings, save } = useContext(SettingsContext);
  const [serverUrl, setServerUrl] = useState(settings.serverUrl);
  const [apiToken, setApiToken] = useState(settings.apiToken);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const handleSave = async () => {
    // Normalize URL
    let url = serverUrl.trim();
    if (url && !url.startsWith('http')) {
      url = `http://${url}`;
    }
    // Strip trailing slash
    url = url.replace(/\/+$/, '');

    await save({ serverUrl: url, apiToken: apiToken.trim() });
    setServerUrl(url);
    setTestResult(null);
    Alert.alert('Saved', 'Server settings updated.');
  };

  const handleTest = async () => {
    if (!serverUrl.trim()) {
      Alert.alert('Error', 'Enter a server URL first.');
      return;
    }

    setTesting(true);
    setTestResult(null);

    try {
      // Temporarily apply settings for the test
      let url = serverUrl.trim();
      if (!url.startsWith('http')) url = `http://${url}`;
      url = url.replace(/\/+$/, '');

      apiClient.setServer(url);
      apiClient.setToken(apiToken.trim());

      const status = await apiClient.getStatus();

      if (status.app === 'Wain') {
        // If auth is required, test an authenticated endpoint
        if (status.auth_required && apiToken.trim()) {
          const workers = await apiClient.getWorkers();
          setTestResult(
            `Connected to Wain v${status.version}\n` +
            `${status.total_jobs} jobs, ${status.active_workers} workers\n` +
            `Authentication: OK`,
          );
        } else if (status.auth_required && !apiToken.trim()) {
          setTestResult(
            `Server found (Wain v${status.version})\n` +
            `Authentication required — enter your API token`,
          );
        } else {
          setTestResult(
            `Connected to Wain v${status.version}\n` +
            `${status.total_jobs} jobs, ${status.active_workers} workers`,
          );
        }
      } else {
        setTestResult('Server responded but is not a Wain server.');
      }
    } catch (e: any) {
      setTestResult(`Failed: ${e.message}`);
      // Restore previous settings
      apiClient.setServer(settings.serverUrl);
      apiClient.setToken(settings.apiToken);
    } finally {
      setTesting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Settings</Text>

        {/* Server URL */}
        <Text style={styles.label}>Server URL</Text>
        <TextInput
          style={styles.input}
          value={serverUrl}
          onChangeText={setServerUrl}
          placeholder="e.g. 192.168.1.10:8080"
          placeholderTextColor={Colors.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <Text style={styles.hint}>
          The IP and port shown when Wain starts in network mode
        </Text>

        {/* API Token */}
        <Text style={styles.label}>API Token</Text>
        <TextInput
          style={styles.input}
          value={apiToken}
          onChangeText={setApiToken}
          placeholder="Paste token from server console"
          placeholderTextColor={Colors.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry={false}
        />
        <Text style={styles.hint}>
          Shown in the server console as "Workers must use: --token ..."
        </Text>

        {/* Buttons */}
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={styles.testButton}
            onPress={handleTest}
            disabled={testing}
          >
            {testing ? (
              <ActivityIndicator size="small" color={Colors.textPrimary} />
            ) : (
              <Text style={styles.testButtonText}>Test Connection</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity style={styles.saveButton} onPress={handleSave}>
            <Text style={styles.saveButtonText}>Save</Text>
          </TouchableOpacity>
        </View>

        {/* Test result */}
        {testResult ? (
          <View style={styles.resultBox}>
            <Text style={styles.resultText}>{testResult}</Text>
          </View>
        ) : null}

        {/* About */}
        <View style={styles.aboutSection}>
          <Text style={styles.aboutTitle}>Wain Mobile Monitor</Text>
          <Text style={styles.aboutText}>
            View your render queue and worker status from your phone.
            {'\n'}Requires Wain running in network mode (--network).
          </Text>
          <Text style={styles.aboutLink}>
            github.com/sbuff25/RenderManager
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  content: {
    padding: 16,
    paddingBottom: 100,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: Colors.textPrimary,
    marginBottom: 24,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textSecondary,
    marginBottom: 6,
    marginTop: 16,
  },
  input: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: Colors.textPrimary,
  },
  hint: {
    fontSize: 11,
    color: Colors.textMuted,
    marginTop: 4,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  testButton: {
    flex: 1,
    backgroundColor: Colors.border,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  testButtonText: {
    color: Colors.textPrimary,
    fontSize: 15,
    fontWeight: '600',
  },
  saveButton: {
    flex: 1,
    backgroundColor: Colors.connected,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  resultBox: {
    backgroundColor: Colors.surface,
    borderRadius: 10,
    padding: 14,
    marginTop: 16,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
  },
  resultText: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 20,
  },
  aboutSection: {
    marginTop: 40,
    alignItems: 'center',
    paddingVertical: 20,
    borderTopWidth: 1,
    borderTopColor: Colors.cardBorder,
  },
  aboutTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.textTertiary,
    marginBottom: 8,
  },
  aboutText: {
    fontSize: 12,
    color: Colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 8,
  },
  aboutLink: {
    fontSize: 12,
    color: Colors.textTertiary,
  },
});
