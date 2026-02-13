import React, { useCallback, useContext } from 'react';
import {
  View,
  Text,
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '../theme/colors';
import { apiClient } from '../api/client';
import { usePolling } from '../hooks/usePolling';
import { StatCard } from '../components/StatCard';
import { JobCard } from '../components/JobCard';
import { ConnectionBanner } from '../components/ConnectionBanner';
import { SettingsContext } from '../SettingsContext';
import type { JobAction } from '../components/JobCard';
import type { RenderJob, ServerStatus, JobsResponse } from '../api/types';

interface DashboardData {
  status: ServerStatus;
  jobs: RenderJob[];
}

const POLL_INTERVAL = 3000; // 3 seconds

const ACTION_CONFIRM: Record<JobAction, { title: string; msg: (name: string) => string }> = {
  pause: {
    title: 'Pause Job',
    msg: (name) => `Pause "${name}"? A rendering job will be stopped at the current frame.`,
  },
  resume: {
    title: 'Resume Job',
    msg: (name) => `Resume "${name}"? It will be re-queued for rendering.`,
  },
  requeue: {
    title: 'Requeue Job',
    msg: (name) => `Requeue "${name}"? All progress will be reset.`,
  },
};

export function DashboardScreen() {
  const { settings } = useContext(SettingsContext);
  const isConfigured = !!settings.serverUrl;

  const fetcher = useCallback(async (): Promise<DashboardData> => {
    const [status, jobsResp] = await Promise.all([
      apiClient.getStatus(),
      apiClient.getJobs(),
    ]);
    return { status, jobs: jobsResp.jobs };
  }, []);

  const { data, loading, error, refresh } = usePolling(
    fetcher,
    POLL_INTERVAL,
    isConfigured,
  );

  const status = data?.status;
  const jobs = data?.jobs || [];

  const rendering = jobs.filter(
    (j) => j.status === 'rendering' || j.status === 'claimed',
  ).length;
  const queued = jobs.filter((j) => j.status === 'queued').length;
  const completed = jobs.filter((j) => j.status === 'completed').length;
  const failed = jobs.filter((j) => j.status === 'failed').length;

  const executeAction = useCallback(async (action: JobAction, job: RenderJob) => {
    try {
      switch (action) {
        case 'pause':
          await apiClient.pauseJob(job.id);
          break;
        case 'resume':
          await apiClient.resumeJob(job.id);
          break;
        case 'requeue':
          await apiClient.requeueJob(job.id);
          break;
      }
      refresh();
    } catch (err: any) {
      Alert.alert('Action Failed', err?.message || 'Could not perform action.');
    }
  }, [refresh]);

  const handleAction = useCallback((action: JobAction, job: RenderJob) => {
    const confirm = ACTION_CONFIRM[action];
    const name = job.name || job.id;
    Alert.alert(confirm.title, confirm.msg(name), [
      { text: 'Cancel', style: 'cancel' },
      { text: confirm.title, onPress: () => executeAction(action, job) },
    ]);
  }, [executeAction]);

  const renderHeader = () => (
    <View>
      {/* Title */}
      <View style={styles.titleRow}>
        <Text style={styles.title}>WAIN</Text>
        {status ? (
          <Text style={styles.version}>v{status.version}</Text>
        ) : null}
      </View>

      <ConnectionBanner error={error} serverUrl={settings.serverUrl} />

      {/* Stat cards */}
      <View style={styles.statsRow}>
        <StatCard label="Rendering" value={rendering} color={Colors.rendering} />
        <StatCard label="Queued" value={queued} color={Colors.queued} />
        <StatCard label="Done" value={completed} color={Colors.completed} />
        <StatCard label="Failed" value={failed} color={Colors.failed} />
      </View>

      {/* Section header */}
      <View style={styles.sectionRow}>
        <Text style={styles.sectionTitle}>Render Queue</Text>
        <Text style={styles.sectionCount}>{jobs.length} jobs</Text>
      </View>
    </View>
  );

  const renderEmpty = () =>
    !loading && isConfigured && !error ? (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>{'{ }'}</Text>
        <Text style={styles.emptyText}>No render jobs</Text>
        <Text style={styles.emptySubtext}>
          Add jobs from the desktop app
        </Text>
      </View>
    ) : null;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={jobs}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <JobCard job={item} onAction={handleAction} />
        )}
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
  titleRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: Colors.textPrimary,
    letterSpacing: 2,
  },
  version: {
    fontSize: 13,
    color: Colors.textMuted,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 20,
  },
  sectionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  sectionCount: {
    fontSize: 13,
    color: Colors.textTertiary,
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
  },
});
