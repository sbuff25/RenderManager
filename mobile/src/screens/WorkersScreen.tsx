import React, { useCallback, useContext } from 'react';
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '../theme/colors';
import { apiClient } from '../api/client';
import { usePolling } from '../hooks/usePolling';
import { WorkerCard } from '../components/WorkerCard';
import { ConnectionBanner } from '../components/ConnectionBanner';
import { SettingsContext } from '../SettingsContext';
import type { Worker } from '../api/types';

const POLL_INTERVAL = 5000; // 5 seconds

export function WorkersScreen() {
  const { settings } = useContext(SettingsContext);
  const isConfigured = !!settings.serverUrl;

  const fetcher = useCallback(async (): Promise<Worker[]> => {
    const resp = await apiClient.getWorkers();
    return resp.workers;
  }, []);

  const { data, loading, error, refresh } = usePolling(
    fetcher,
    POLL_INTERVAL,
    isConfigured,
  );

  const workers = data || [];
  const connected = workers.filter(
    (w) => !w.is_stale && w.status !== 'offline',
  ).length;
  const offline = workers.length - connected;

  const renderHeader = () => (
    <View>
      <Text style={styles.title}>Workers</Text>

      <ConnectionBanner error={error} serverUrl={settings.serverUrl} />

      {/* Summary row */}
      {workers.length > 0 ? (
        <View style={styles.summaryRow}>
          {connected > 0 ? (
            <Text style={[styles.summaryText, { color: Colors.positive }]}>
              {connected} connected
            </Text>
          ) : null}
          {offline > 0 ? (
            <Text style={[styles.summaryText, { color: Colors.offline }]}>
              {offline} offline
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );

  const renderEmpty = () =>
    !loading && isConfigured && !error ? (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>{'{ }'}</Text>
        <Text style={styles.emptyText}>No workers</Text>
        <Text style={styles.emptySubtext}>
          Start a worker with:{'\n'}python -m wain --worker --server {'<ip>'}:8080
        </Text>
      </View>
    ) : null;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={workers}
        keyExtractor={(item) => item.worker_id}
        renderItem={({ item }) => <WorkerCard worker={item} />}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={false}
            onRefresh={refresh}
            tintColor={Colors.textSecondary}
          />
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  list: {
    padding: 16,
    paddingBottom: 100,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: Colors.textPrimary,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 16,
  },
  summaryText: {
    fontSize: 13,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyIcon: {
    fontSize: 40,
    color: Colors.textMuted,
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 18,
    color: Colors.textTertiary,
    marginBottom: 4,
  },
  emptySubtext: {
    fontSize: 13,
    color: Colors.textMuted,
    textAlign: 'center',
    lineHeight: 20,
  },
});
