import { DataQuery, DataSourceJsonData } from '@grafana/data';

/**
 * Query configuration for Dynatrace metrics
 */
export interface MyQuery extends DataQuery {
  // Metric ID from Dynatrace (e.g., "builtin:host.cpu.usage")
  metricId?: string;
  
  // Entity selector to filter metrics (e.g., "type(HOST),entityName.equals(myhost)")
  entitySelector?: string;
  
  // Use dashboard time range instead of custom time range
  useDashboardTime: boolean;
  
  // Custom time range (only used when useDashboardTime is false)
  customFrom?: string;
  customTo?: string;
  
  // Resolution for data points (e.g., "1m", "5m", "1h")
  resolution?: string;
}

export const DEFAULT_QUERY: Partial<MyQuery> = {
  useDashboardTime: true,
  resolution: '5m',
  metricId: '',
};

/**
 * These are options configured for each DataSource instance
 */
export interface MyDataSourceOptions extends DataSourceJsonData {
  // Base URL for Dynatrace API (e.g., "http://localhost:8080")
  apiUrl?: string;
}

/**
 * Value that is used in the backend, but never sent over HTTP to the frontend
 */
export interface MySecureJsonData {
  // Dynatrace API Token (Api-Token format)
  apiToken?: string;
}
