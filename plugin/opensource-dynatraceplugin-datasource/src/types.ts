import { DataQuery, DataSourceJsonData } from '@grafana/data';

/**
 * Query configuration for Dynatrace metrics
 */
// Type of query.
//   - 'metrics'  : classic /api/v2/metrics/query
//   - 'logs'     : legacy /api/v2/logs/search (Log Search Query syntax)
//   - 'alerts'   : /api/v2/problems
//   - 'dqlGrail' : new Grail /platform/storage/query/v1/query:execute (full DQL)
//                  Returned in the same Loki frame format as 'logs'.
export type QueryType = 'metrics' | 'logs' | 'alerts' | 'dqlGrail';

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

  // ---- Grail DQL fields (used when queryType === 'dqlGrail') ----
  // Full DQL pipeline executed on Grail. Example:
  //   fetch logs | filter k8s.container.name == "x" | summarize count() by content
  dqlQuery?: string;
  // Max records the Grail engine should return (default 1000).
  dqlLimit?: number;

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
  dqlQuery: '',
  dqlLimit: 1000,
  alertSelector: '',
  alertPageSize: 50,
};

/**
 * These are options configured for each DataSource instance
 */
export interface MyDataSourceOptions extends DataSourceJsonData {
  // Classic API URL (e.g. https://<tenant>.live.dynatrace.com). Used for
  // /api/v2/metrics, /api/v2/problems and the legacy /api/v2/logs/search.
  apiUrl?: string;

  // Platform API URL (e.g. https://<tenant>.apps.dynatrace.com). Used for
  // Grail endpoints — currently DQL (/platform/storage/query/v1/...).
  // Optional: when blank, the plugin falls back to apiUrl (matches the
  // single-host simulator and Classic-only tenants).
  platformUrl?: string;

  // Skip TLS certificate verification (insecure)
  tlsSkipVerify?: boolean;
}

/**
 * Value that is used in the backend, but never sent over HTTP to the frontend
 */
export interface MySecureJsonData {
  // Classic Dynatrace API Token (used for /api/v2/metrics/query and other
  // Classic endpoints). Sent as `Authorization: Api-Token <value>`.
  apiToken?: string;

  // Dynatrace Platform Token (used by Grail endpoints — Logs Search, DQL,
  // Problems on Grail-migrated tenants). Sent as `Authorization: Bearer <value>`.
  // Optional: when not set the plugin falls back to the API Token above.
  // See: https://docs.dynatrace.com/docs/manage/identity-access-management/access-tokens-and-oauth-clients/platform-tokens
  platformToken?: string;

  // TLS client certificate (PEM format)
  tlsCertificate?: string;
}
