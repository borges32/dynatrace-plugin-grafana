import React, { ChangeEvent } from 'react';
import { InlineField, Input, InlineSwitch, Select, TextArea } from '@grafana/ui';
import { QueryEditorProps, SelectableValue } from '@grafana/data';
import { DataSource } from '../datasource';
import { MyDataSourceOptions, MyQuery } from '../types';

type Props = QueryEditorProps<DataSource, MyQuery, MyDataSourceOptions>;

const QUERY_TYPE_OPTIONS: Array<SelectableValue<string>> = [
  { label: 'Metrics', value: 'metrics' },
  { label: 'Logs (Loki format)', value: 'logs' },
  { label: 'Alerts (Problems)', value: 'alerts' },
];

const RESOLUTION_OPTIONS: Array<SelectableValue<string>> = [
  { label: '1 minute', value: '1m' },
  { label: '5 minutes', value: '5m' },
  { label: '10 minutes', value: '10m' },
  { label: '30 minutes', value: '30m' },
  { label: '1 hour', value: '1h' },
  { label: '1 day', value: '1d' },
];

export function QueryEditor({ query, onChange, onRunQuery }: Props) {
  // Metric Selector handler (primary field)
  const onMetricSelectorChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onChange({ ...query, metricSelector: event.target.value });
  };

  // Use Dashboard Time toggle handler
  const onUseDashboardTimeChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange({ ...query, useDashboardTime: event.currentTarget.checked });
  };

  // Custom From timestamp handler
  const onCustomFromChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange({ ...query, customFrom: event.target.value });
  };

  // Custom To timestamp handler
  const onCustomToChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange({ ...query, customTo: event.target.value });
  };

  // Resolution handler
  const onResolutionChange = (option: SelectableValue<string>) => {
    onChange({ ...query, resolution: option.value });
    onRunQuery();
  };

  // Label Chart handler
  const onLabelChartChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange({ ...query, labelChart: event.target.value });
  };

  // Query Type handler (metrics vs. logs)
  const onQueryTypeChange = (option: SelectableValue<string>) => {
    onChange({ ...query, queryType: (option.value as 'metrics' | 'logs') || 'metrics' });
    onRunQuery();
  };

  // Log query handlers
  const onLogQueryChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onChange({ ...query, logQuery: event.target.value });
  };

  const onLogLimitChange = (event: ChangeEvent<HTMLInputElement>) => {
    const n = parseInt(event.target.value, 10);
    onChange({ ...query, logLimit: isNaN(n) ? undefined : n });
  };

  // Alert query handlers
  const onAlertSelectorChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onChange({ ...query, alertSelector: event.target.value });
  };

  const onAlertPageSizeChange = (event: ChangeEvent<HTMLInputElement>) => {
    const n = parseInt(event.target.value, 10);
    onChange({ ...query, alertPageSize: isNaN(n) ? undefined : n });
  };

  const queryType = query.queryType || 'metrics';
  const { metricSelector, useDashboardTime, customFrom, customTo, resolution, labelChart, logQuery, logLimit, alertSelector, alertPageSize } = query;

  return (
    <div className="gf-form-group">
      <h6 className="page-heading">
        Dynatrace {queryType === 'logs' ? 'Logs' : queryType === 'alerts' ? 'Alerts' : 'Metric'} Query
      </h6>

      <div className="gf-form">
        <InlineField
          label="Query Type"
          labelWidth={20}
          tooltip="Choose Metrics (default) or Logs (Dynatrace /api/v2/logs/search, returned in Loki format)"
        >
          <Select
            options={QUERY_TYPE_OPTIONS}
            value={queryType}
            onChange={onQueryTypeChange}
            width={28}
          />
        </InlineField>
      </div>

      {queryType === 'logs' && (
        <>
          <div className="gf-form">
            <InlineField
              label="Log Query"
              labelWidth={20}
              tooltip='Dynatrace log search query. Supports free text and key=value filters (e.g. host.name="host-prod-01" status=ERROR).'
              grow
            >
              <div style={{ width: '100%' }}>
                <TextArea
                  onChange={onLogQueryChange}
                  onBlur={onRunQuery}
                  value={logQuery || ''}
                  placeholder={'ERROR\nor with filters:\nhost.name="host-prod-01" status=ERROR'}
                  rows={3}
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: '13px' }}
                />
                <div style={{ marginTop: '4px', fontSize: '11px', color: '#888' }}>
                  Examples:
                  <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                    <li><code>ERROR</code></li>
                    <li><code>status=ERROR</code></li>
                    <li><code>host.name=&quot;host-prod-01&quot; service.name=&quot;api-gateway&quot;</code></li>
                  </ul>
                </div>
              </div>
            </InlineField>
          </div>

          <div className="gf-form">
            <InlineField label="Limit" labelWidth={20} tooltip="Maximum number of log records (default 1000, max 10000)">
              <Input
                type="number"
                onChange={onLogLimitChange}
                onBlur={onRunQuery}
                value={logLimit ?? 1000}
                placeholder="1000"
                width={20}
              />
            </InlineField>
          </div>
        </>
      )}

      {queryType === 'alerts' && (
        <>
          <div className="gf-form">
            <InlineField
              label="Problem Selector"
              labelWidth={20}
              tooltip='Dynatrace problemSelector mini-DSL (status("OPEN"),severityLevel("ERROR"),...) OR a DQL pipeline (fetch dt.davis.problems | filter ... | sort ... | limit N).'
              grow
            >
              <div style={{ width: '100%' }}>
                <TextArea
                  onChange={onAlertSelectorChange}
                  onBlur={onRunQuery}
                  value={alertSelector || ''}
                  placeholder={'status("OPEN"),severityLevel("ERROR")\nor DQL:\nfetch dt.davis.problems | filter event.status == "OPEN" | sort startTime desc'}
                  rows={3}
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: '13px' }}
                />
                <div style={{ marginTop: '4px', fontSize: '11px', color: '#888' }}>
                  Examples:
                  <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                    <li><code>status(&quot;OPEN&quot;)</code></li>
                    <li><code>status(&quot;OPEN&quot;),severityLevel(&quot;ERROR&quot;,&quot;AVAILABILITY&quot;)</code></li>
                    <li><code>entityTags(&quot;env:prod&quot;),managementZones(&quot;Production&quot;)</code></li>
                    <li><code>fetch dt.davis.problems | filter event.status == &quot;OPEN&quot; | sort startTime desc | limit 50</code></li>
                  </ul>
                </div>
              </div>
            </InlineField>
          </div>

          <div className="gf-form">
            <InlineField label="Page Size" labelWidth={20} tooltip="Maximum number of problems (default 50, max 500)">
              <Input
                type="number"
                onChange={onAlertPageSizeChange}
                onBlur={onRunQuery}
                value={alertPageSize ?? 50}
                placeholder="50"
                width={20}
              />
            </InlineField>
          </div>
        </>
      )}

      {queryType === 'metrics' && (
      <>
      <div className="gf-form">
        <InlineField
          label="Metric Selector"
          labelWidth={20}
          tooltip="Dynatrace Metric Selector with filters and transformations"
          grow
        >
          <div style={{ width: '100%' }}>
            <TextArea
              onChange={onMetricSelectorChange}
              onBlur={onRunQuery}
              value={metricSelector || ''}
              placeholder="builtin:host.cpu.usage&#10;or with filters:&#10;builtin:apps.other.crashCount:filter(...):splitBy():sort(...)"
              rows={3}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: '13px' }}
            />
            <div style={{ marginTop: '4px', fontSize: '11px', color: '#888' }}>
              Examples:
              <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                <li><code>builtin:host.cpu.usage</code></li>
                <li><code>builtin:host.cpu.usage:filter(eq(dt.entity.host,HOST-123))</code></li>
                <li><code>builtin:apps.other.crashCount.osAndVersion:filter(...):splitBy():sort(value(auto,descending))</code></li>
              </ul>
            </div>
          </div>
        </InlineField>
      </div>

      <div className="gf-form">
        <InlineField 
          label="Resolution" 
          labelWidth={20}
          tooltip="Data point resolution"
        >
          <Select
            options={RESOLUTION_OPTIONS}
            value={resolution}
            onChange={onResolutionChange}
            width={20}
          />
        </InlineField>
      </div>

      <div className="gf-form">
        <InlineField 
          label="Label Chart" 
          labelWidth={20}
          tooltip="Specify which label field to use for chart legend (e.g., dt.entity.service_method.name). Leave empty to use default."
          grow
        >
          <Input
            onChange={onLabelChartChange}
            onBlur={onRunQuery}
            value={labelChart || ''}
            placeholder="dt.entity.service_method.name"
          />
        </InlineField>
      </div>
      </>
      )}

      <div className="gf-form">
        <InlineField
          label="Use Dashboard Time"
          labelWidth={20}
          tooltip="When enabled, uses the time range from the dashboard. When disabled, uses custom time range."
        >
          <InlineSwitch
            value={useDashboardTime}
            onChange={onUseDashboardTimeChange}
          />
        </InlineField>
      </div>

      {!useDashboardTime && (
        <>
          <div className="gf-form">
            <InlineField 
              label="Custom From" 
              labelWidth={20}
              tooltip="Start timestamp in milliseconds (e.g., 1699500000000) or relative time (e.g., now-1h)"
            >
              <Input
                onChange={onCustomFromChange}
                onBlur={onRunQuery}
                value={customFrom || ''}
                placeholder="1699500000000 or now-1h"
                width={30}
              />
            </InlineField>
          </div>

          <div className="gf-form">
            <InlineField 
              label="Custom To" 
              labelWidth={20}
              tooltip="End timestamp in milliseconds (e.g., 1699503600000) or relative time (e.g., now)"
            >
              <Input
                onChange={onCustomToChange}
                onBlur={onRunQuery}
                value={customTo || ''}
                placeholder="1699503600000 or now"
                width={30}
              />
            </InlineField>
          </div>
        </>
      )}
    </div>
  );
}
