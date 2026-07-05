import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';

export type MetricItemProps = {
  label: string;
  value: string | number;
  highlight?: boolean;
  onPress?: () => void;
};

type DarkMetricPanelProps = {
  title: string;
  subtitle?: string;
  metrics: MetricItemProps[];
};

export function DarkMetricPanel({ title, subtitle, metrics }: DarkMetricPanelProps) {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      </View>
      
      <View style={styles.grid}>
        {metrics.map((metric, index) => {
          const content = (
            <View style={styles.metricCell}>
              <Text style={[styles.value, metric.highlight && styles.valueHighlight]}>
                {metric.value}
              </Text>
              <Text style={styles.label}>{metric.label}</Text>
            </View>
          );

          return metric.onPress ? (
            <Pressable 
              key={index} 
              style={({ pressed }) => [styles.metricWrapper, pressed && styles.metricPressed]}
              onPress={metric.onPress}
            >
              {content}
            </Pressable>
          ) : (
            <View key={index} style={styles.metricWrapper}>
              {content}
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#111111',
    borderRadius: 20,
    padding: 18,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  subtitle: {
    color: 'rgba(255,255,255,0.60)',
    fontSize: 12,
    fontWeight: '500',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -8, // compensate for wrapper padding
  },
  metricWrapper: {
    width: '50%',
    paddingHorizontal: 8,
    marginBottom: 16,
  },
  metricPressed: {
    opacity: 0.7,
  },
  metricCell: {
    justifyContent: 'flex-start',
  },
  value: {
    color: '#FFFFFF',
    fontSize: 24,
    fontWeight: '700',
    letterSpacing: -0.72, // -0.03em
    marginBottom: 2,
  },
  valueHighlight: {
    color: '#B7F52A',
  },
  label: {
    color: 'rgba(255,255,255,0.60)',
    fontSize: 12,
    fontWeight: '500',
  }
});
