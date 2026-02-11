import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '../theme/colors';

interface Props {
  error: string | null;
  serverUrl: string;
}

export function ConnectionBanner({ error, serverUrl }: Props) {
  if (!serverUrl) {
    return (
      <View style={[styles.banner, { backgroundColor: '#422006' }]}>
        <Text style={styles.text}>
          No server configured — go to Settings to connect
        </Text>
      </View>
    );
  }
  if (error) {
    return (
      <View style={[styles.banner, { backgroundColor: '#450a0a' }]}>
        <Text style={styles.text}>
          Connection failed: {error}
        </Text>
      </View>
    );
  }
  return null;
}

const styles = StyleSheet.create({
  banner: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    marginBottom: 12,
  },
  text: {
    color: Colors.textSecondary,
    fontSize: 13,
    textAlign: 'center',
  },
});
