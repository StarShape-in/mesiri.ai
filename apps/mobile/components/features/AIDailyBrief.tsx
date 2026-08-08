import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Sparkles } from 'lucide-react-native';

type AIDailyBriefProps = {
  brief: string;
};

export function AIDailyBrief({ brief }: AIDailyBriefProps) {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>AI Daily Brief</Text>
        <Sparkles size={14} color="#B7F52A" fill="#B7F52A" style={styles.icon} />
      </View>
      <Text style={styles.briefText} numberOfLines={6}>
        {brief}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111111',
  },
  icon: {
    marginLeft: 6,
  },
  briefText: {
    fontSize: 14,
    lineHeight: 22,
    color: '#525252',
    fontWeight: '400',
  }
});
