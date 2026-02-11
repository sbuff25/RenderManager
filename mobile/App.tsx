/**
 * Wain Mobile — Monitor render jobs from your phone
 *
 * https://github.com/sbuff25/RenderManager
 */

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Text, StyleSheet } from 'react-native';

import { SettingsContext } from './src/SettingsContext';
import { useSettings } from './src/hooks/useSettings';
import { DashboardScreen } from './src/screens/DashboardScreen';
import { WorkersScreen } from './src/screens/WorkersScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { Colors } from './src/theme/colors';

const Tab = createBottomTabNavigator();

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  const icons: Record<string, string> = {
    Dashboard: '⊞',
    Workers: '⊟',
    Settings: '⊙',
  };
  return (
    <Text style={[styles.tabIcon, focused && styles.tabIconFocused]}>
      {icons[label] || '○'}
    </Text>
  );
}

export default function App() {
  const { settings, save, loaded } = useSettings();

  if (!loaded) return null;

  return (
    <SafeAreaProvider>
      <SettingsContext.Provider value={{ settings, save, loaded }}>
        <NavigationContainer
          theme={{
            dark: true,
            colors: {
              primary: Colors.textPrimary,
              background: Colors.bg,
              card: Colors.surface,
              text: Colors.textPrimary,
              border: Colors.cardBorder,
              notification: Colors.rendering,
            },
            fonts: {
              regular: { fontFamily: 'System', fontWeight: '400' },
              medium: { fontFamily: 'System', fontWeight: '500' },
              bold: { fontFamily: 'System', fontWeight: '700' },
              heavy: { fontFamily: 'System', fontWeight: '800' },
            },
          }}
        >
          <Tab.Navigator
            screenOptions={({ route }) => ({
              headerShown: false,
              tabBarStyle: styles.tabBar,
              tabBarActiveTintColor: Colors.textPrimary,
              tabBarInactiveTintColor: Colors.textMuted,
              tabBarIcon: ({ focused }) => (
                <TabIcon label={route.name} focused={focused} />
              ),
              tabBarLabelStyle: styles.tabLabel,
            })}
          >
            <Tab.Screen name="Dashboard" component={DashboardScreen} />
            <Tab.Screen name="Workers" component={WorkersScreen} />
            <Tab.Screen name="Settings" component={SettingsScreen} />
          </Tab.Navigator>
        </NavigationContainer>
        <StatusBar style="light" />
      </SettingsContext.Provider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: Colors.surface,
    borderTopColor: Colors.cardBorder,
    borderTopWidth: 1,
    paddingBottom: 4,
    height: 56,
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
  },
  tabIcon: {
    fontSize: 22,
    color: Colors.textMuted,
  },
  tabIconFocused: {
    color: Colors.textPrimary,
  },
});
