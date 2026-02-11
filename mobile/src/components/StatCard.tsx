import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '../theme/colors';

interface Props {
  label: string;
  value: number;
  color: string;
}

export function StatCard({ label, value, color }: Props) {
  return (
    <View style={[styles.card, { borderTopColor: color }]}>
      <Text style={[styles.value, { color }]}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderTopWidth: 3,
    paddingVertical: 14,
    paddingHorizontal: 10,
    alignItems: 'center',
    minWidth: 70,
  },
  value: {
    fontSize: 28,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  label: {
    fontSize: 11,
    color: Colors.textSecondary,
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
