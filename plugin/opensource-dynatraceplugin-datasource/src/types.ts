import { DataQuery, DataSourceJsonData } from '@grafana/data';

/**
 * Query configuration for Dynatrace metrics
 */
// Type of query: classic Dynatrace metrics, logs (returned in Loki format) or alerts (problems).
export type QueryType = 'metrics' | 'logs' | 'alerts';

export interface MyQuery extends DataQuery {
  // Discriminator between metric and log queries. Defaults to 'metrics' for backward compatibility.
  queryType?: QueryType;

  // ---- Logs fields (used when queryType === 'logs') ----
  // Dynatrace logs query string (simplified DQL). Examples:
  //   "ERROR"
  //   "host.name=\"host-prod-01\" status=ERROR"
  logQuery?: string;
  // Max records to fetch (default 1000)
  logLimit?: number;

  // ---- Alerts fields (used when queryType === 'alerts') ----
  // Dynatrace problemSelector (mini-DSL) OR DQL pipeline. Examples:
  //   status("OPEN"),severityLevel("ERROR")
  //   fetch dt.davis.problems | filter event.status == "OPEN" | sort startTime desc | limit 50
  alertSelector?: string;
  // Max problems to fetch (default 50)
  alertPageSize?: number;

  // Metric selector with transformations (e.g., "builtin:host.cpu.usage:filter(...):splitBy()")
  // This is the primary field for querying metrics with complex filters
  metricSelector?: string;
  
  // DEPRECATED: Use metricSelector instead
  // Kept for backward compatibility
  metricId?: string;
  
  // DEPRECATED: Use filters in metricSelector instead
  // Entity selector to filter metrics (e.g., "type(HOST),entityName.equals(myhost)")
  entitySelector?: string;
  
  // Use dashboard time range instead of custom time range
  useDashboardTime: boolean;
  
  // Custom time range (only used when useDashboardTime is false)
  customFrom?: string;
  customTo?: string;
  
  // Resolution for data points (e.g., "1m", "5m", "1h")
  resolution?: string;
  
  // Label Chart - field from labels to use for chart legend
  // (e.g., "dt.entity.service_method.name")
  labelChart?: string;
}

export const DEFAULT_QUERY: Partial<MyQuery> = {
  queryType: 'metrics',
  useDashboardTime: true,
  resolution: '5m',
  metricSelector: '',
  logQuery: '',
  logLimit: 1000,
  alertSelector: '',
  alertPageSize: 50,
};

/**
 * These are options configured for each DataSource instance
 */
export interface MyDataSourceOptions extends DataSourceJsonData {
  // Base URL for Dynatrace API (e.g., "http://localhost:8080")
  apiUrl?: string;
  
  // Skip TLS certificate verification (insecure)
  tlsSkipVerify?: boolean;
}

/**
 * Value that is used in the backend, but never sent over HTTP to the frontend
 */
export interface MySecureJsonData {
  // Dynatrace API Token (Api-Token format)
  apiToken?: string;
  
  // TLS client certificate (PEM format)
  tlsCertificate?: string;
}
