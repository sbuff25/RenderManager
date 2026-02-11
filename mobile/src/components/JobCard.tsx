import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, engineColor, statusColor } from '../theme/colors';
import { ProgressBar } from './ProgressBar';
import type { RenderJob } from '../api/types';

interface Props {
  job: RenderJob;
}

function framesDisplay(job: RenderJob): string {
  if (job.is_animation) {
    const frame = job.rendering_frame > 0 ? job.rendering_frame : job.current_frame;
    if (frame > 0 && frame >= job.frame_start) {
      return `${frame}/${job.frame_end}`;
    }
    return `0/${job.frame_end}`;
  }
  return '';
}

function samplesDisplay(job: RenderJob): string {
  if (job.current_sample > 0 && job.total_samples > 0) {
    const pct = Math.min(
      Math.floor((job.current_sample / job.total_samples) * 100),
      99,
    );
    return `Frame ${pct}%`;
  }
  return '';
}

export function JobCard({ job }: Props) {
  const eColor = engineColor(job.engine_type);
  const sColor = statusColor(job.status);
  const frames = framesDisplay(job);
  const samples = samplesDisplay(job);
  const fileName = job.file_path
    ? job.file_path.split(/[\\/]/).pop() || ''
    : '';

  return (
    <View style={[styles.card, { borderLeftColor: eColor }]}>
      {/* Header row */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Text style={styles.name} numberOfLines={1}>
            {job.name || job.id}
          </Text>
          <View style={[styles.engineBadge, { backgroundColor: eColor + '22' }]}>
            <Text style={[styles.engineText, { color: eColor }]}>
              {job.engine_type.toUpperCase()}
            </Text>
          </View>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: sColor + '22' }]}>
          <Text style={[styles.statusText, { color: sColor }]}>
            {job.status.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* File name */}
      {fileName ? (
        <Text style={styles.fileName} numberOfLines={1}>
          {fileName}
        </Text>
      ) : null}

      {/* Progress bar */}
      <View style={styles.progressRow}>
        <ProgressBar
          progress={job.progress}
          color={job.status === 'rendering' ? eColor : sColor}
        />
        <Text style={styles.progressPct}>{job.progress}%</Text>
      </View>

      {/* Details row */}
      <View style={styles.detailsRow}>
        {frames ? <Text style={styles.detail}>Frame {frames}</Text> : null}
        {samples ? <Text style={styles.detail}>{samples}</Text> : null}
        {job.elapsed_time ? (
          <Text style={styles.detail}>{job.elapsed_time}</Text>
        ) : null}
        {job.assigned_to ? (
          <Text style={styles.detail}>@ {job.assigned_to}</Text>
        ) : null}
      </View>

      {/* Status message */}
      {job.status_message && job.status === 'rendering' ? (
        <Text style={styles.statusMsg} numberOfLines={1}>
          {job.status_message}
        </Text>
      ) : null}

      {/* Error */}
      {job.error_message && job.status === 'failed' ? (
        <Text style={styles.error} numberOfLines={2}>
          {job.error_message}
        </Text>
      ) : null}
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
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 8,
  },
  name: {
    fontSize: 15,
    fontWeight: '600',
    color: Colors.textPrimary,
    flexShrink: 1,
  },
  engineBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  engineText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginLeft: 8,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  fileName: {
    fontSize: 12,
    color: Colors.textTertiary,
    marginBottom: 8,
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  progressPct: {
    fontSize: 12,
    color: Colors.textSecondary,
    fontVariant: ['tabular-nums'],
    width: 36,
    textAlign: 'right',
  },
  detailsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  detail: {
    fontSize: 11,
    color: Colors.textTertiary,
  },
  statusMsg: {
    fontSize: 11,
    color: Colors.textTertiary,
    fontStyle: 'italic',
    marginTop: 4,
  },
  error: {
    fontSize: 11,
    color: Colors.negative,
    marginTop: 4,
  },
});
