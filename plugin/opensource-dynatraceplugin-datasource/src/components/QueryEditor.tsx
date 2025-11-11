import React, { ChangeEvent } from 'react';
import { InlineField, Input, InlineSwitch, Select, TextArea } from '@grafana/ui';
import { QueryEditorProps, SelectableValue } from '@grafana/data';
import { DataSource } from '../datasource';
import { MyDataSourceOptions, MyQuery } from '../types';

type Props = QueryEditorProps<DataSource, MyQuery, MyDataSourceOptions>;

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

  const { metricSelector, useDashboardTime, customFrom, customTo, resolution } = query;

  return (
    <div className="gf-form-group">
      <h6 className="page-heading">Dynatrace Metric Query</h6>
      
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
