import React, { ChangeEvent } from 'react';
import { InlineField, Input, SecretInput } from '@grafana/ui';
import { DataSourcePluginOptionsEditorProps } from '@grafana/data';
import { MyDataSourceOptions, MySecureJsonData } from '../types';

interface Props extends DataSourcePluginOptionsEditorProps<MyDataSourceOptions> {}

export function ConfigEditor(props: Props) {
  const { onOptionsChange, options } = props;
  
  // API URL handler
  const onApiUrlChange = (event: ChangeEvent<HTMLInputElement>) => {
    const jsonData = {
      ...options.jsonData,
      apiUrl: event.target.value,
    };
    onOptionsChange({ ...options, jsonData });
  };

  // API Token handler (secure field - only sent to the backend)
  const onApiTokenChange = (event: ChangeEvent<HTMLInputElement>) => {
    onOptionsChange({
      ...options,
      secureJsonData: {
        apiToken: event.target.value,
      },
    });
  };

  const onResetApiToken = () => {
    onOptionsChange({
      ...options,
      secureJsonFields: {
        ...options.secureJsonFields,
        apiToken: false,
      },
      secureJsonData: {
        ...options.secureJsonData,
        apiToken: '',
      },
    });
  };

  const { jsonData, secureJsonFields } = options;
  const secureJsonData = (options.secureJsonData || {}) as MySecureJsonData;

  return (
    <div className="gf-form-group">
      <h3 className="page-heading">Dynatrace API Configuration</h3>
      
      <InlineField 
        label="API URL" 
        labelWidth={20}
        tooltip="Base URL for Dynatrace Metrics V2 API (e.g., http://localhost:8080 or https://your-dynatrace-instance.com)"
      >
        <Input
          onChange={onApiUrlChange}
          value={jsonData.apiUrl || ''}
          placeholder="http://localhost:8080"
          width={60}
          required
        />
      </InlineField>

      <InlineField 
        label="API Token" 
        labelWidth={20}
        tooltip="Dynatrace API Token for authentication (will be sent as 'Api-Token' header)"
      >
        <SecretInput
          isConfigured={(secureJsonFields && secureJsonFields.apiToken) as boolean}
          value={secureJsonData.apiToken || ''}
          placeholder="Enter your Dynatrace API token"
          width={60}
          onReset={onResetApiToken}
          onChange={onApiTokenChange}
          required
        />
      </InlineField>
    </div>
  );
}
