import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '../theme/colors';
import type { Worker } from '../api/types';

interface Props {
  worker: Worker;
}

export function WorkerCard({ worker }: Props) {
  const isOffline = worker.is_stale || worker.status === 'offline';
  const isRendering = worker.status === 'rendering';

  let statusLabel: string;
  let statusClr: string;
  let borderClr: string;

  if (isOffline) {
    statusLabel = 'OFFLINE';
    statusClr = Colors.offline;
    borderClr = Colors.cardBorder;
  } else if (isRendering) {
    statusLabel = 'RENDERING';
    statusClr = Colors.positive;
    borderClr = '#166534';
  } else {
    statusLabel = 'CONNECTED';
    statusClr = Colors.connected;
    borderClr = '#1e3a5f';
  }

  return (
    <View style={[styles.card, { borderLeftColor: borderClr }]}>
      <View style={styles.row}>
        <View style={styles.info}>
          <Text style={styles.name}>{worker.worker_id}</Text>
          <Text style={styles.host}>
            {worker.hostname} ({worker.ip_address})
          </Text>
          {isOffline && worker.last_heartbeat ? (
            <Text style={styles.lastSeen}>
              Last seen: {worker.last_heartbeat}
            </Text>
          ) : null}
        </View>
        <View style={styles.right}>
          <Text style={[styles.status, { color: statusClr }]}>
            {statusLabel}
          </Text>
          {worker.current_job_id && isRendering ? (
            <Text style={styles.jobId}>Job: {worker.current_job_id}</Text>
          ) : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderLeftWidth: 4,
    padding: 14,
    marginBottom: 10,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  info: {
    flex: 1,
  },
  name: {
    fontSize: 15,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  host: {
    fontSize: 12,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  lastSeen: {
    fontSize: 10,
    color: Colors.textMuted,
    marginTop: 2,
  },
  right: {
    alignItems: 'flex-end',
    marginLeft: 12,
  },
  status: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  jobId: {
    fontSize: 10,
    color: Colors.textMuted,
    marginTop: 4,
  },
});
