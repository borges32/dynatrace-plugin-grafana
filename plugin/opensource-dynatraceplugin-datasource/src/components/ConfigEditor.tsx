import React, { ChangeEvent } from 'react';
import { InlineField, Input, SecretInput, InlineSwitch, TextArea } from '@grafana/ui';
import { DataSourcePluginOptionsEditorProps } from '@grafana/data';
import { MyDataSourceOptions, MySecureJsonData } from '../types';

interface Props extends DataSourcePluginOptionsEditorProps<MyDataSourceOptions> {}

export function ConfigEditor(props: Props) {
  const { onOptionsChange, options } = props;
  
  // Classic API URL handler
  const onApiUrlChange = (event: ChangeEvent<HTMLInputElement>) => {
    const jsonData = {
      ...options.jsonData,
      apiUrl: event.target.value,
    };
    onOptionsChange({ ...options, jsonData });
  };

  // Platform API URL handler (Grail)
  const onPlatformUrlChange = (event: ChangeEvent<HTMLInputElement>) => {
    const jsonData = {
      ...options.jsonData,
      platformUrl: event.target.value,
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

  // TLS Skip Verify handler
  const onTlsSkipVerifyChange = (event: ChangeEvent<HTMLInputElement>) => {
    const jsonData = {
      ...options.jsonData,
      tlsSkipVerify: event.currentTarget.checked,
    };
    onOptionsChange({ ...options, jsonData });
  };

  // TLS Certificate handler
  const onTlsCertificateChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onOptionsChange({
      ...options,
      secureJsonData: {
        ...options.secureJsonData,
        tlsCertificate: event.target.value,
      },
    });
  };

  const onResetTlsCertificate = () => {
    onOptionsChange({
      ...options,
      secureJsonFields: {
        ...options.secureJsonFields,
        tlsCertificate: false,
      },
      secureJsonData: {
        ...options.secureJsonData,
        tlsCertificate: '',
      },
    });
  };

  // ---- Platform Token handlers ----
  const onPlatformTokenChange = (event: ChangeEvent<HTMLInputElement>) => {
    onOptionsChange({
      ...options,
      secureJsonData: {
        ...options.secureJsonData,
        platformToken: event.target.value,
      },
    });
  };

  const onResetPlatformToken = () => {
    onOptionsChange({
      ...options,
      secureJsonFields: { ...options.secureJsonFields, platformToken: false },
      secureJsonData: { ...options.secureJsonData, platformToken: '' },
    });
  };

  const { jsonData, secureJsonFields } = options;
  const secureJsonData = (options.secureJsonData || {}) as MySecureJsonData;

  return (
    <div className="gf-form-group">
      <h3 className="page-heading">Dynatrace API Configuration</h3>
      
      <InlineField
        label="Classic API URL"
        labelWidth={20}
        tooltip="Base URL for Classic Dynatrace endpoints (metrics, problems, legacy logs). Example: https://<tenant>.live.dynatrace.com"
      >
        <Input
          onChange={onApiUrlChange}
          value={jsonData.apiUrl || ''}
          placeholder="https://<tenant>.live.dynatrace.com"
          width={60}
          required
        />
      </InlineField>

      <InlineField
        label="Platform API URL"
        labelWidth={20}
        tooltip="Base URL for Grail/Platform endpoints (DQL). Example: https://<tenant>.apps.dynatrace.com. Leave blank for Classic-only tenants or the simulator — Classic URL is reused in that case."
      >
        <Input
          onChange={onPlatformUrlChange}
          value={jsonData.platformUrl || ''}
          placeholder="https://<tenant>.apps.dynatrace.com (Grail)"
          width={60}
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

      <h3 className="page-heading">Platform Token (Grail)</h3>
      <div style={{ fontSize: '12px', color: '#888', marginBottom: '8px' }}>
        Required by Grail-migrated tenants for Logs (Search Query), DQL (Grail)
        and Problems. The Platform Token is created in Dynatrace under{' '}
        <em>Account Management → Access tokens → Platform tokens</em> with the
        needed Grail permissions (e.g. <code>storage:logs:read</code>,{' '}
        <code>storage:events:read</code>, <code>storage:bizevents:read</code>).
        Sent as <code>Authorization: Bearer &lt;token&gt;</code>. Leave empty if
        your tenant is Classic — the API Token above is then used for every
        endpoint.
      </div>

      <InlineField
        label="Platform Token"
        labelWidth={20}
        tooltip="Dynatrace Platform Token (dt0s16.*). Used as Bearer for Grail endpoints (logs/DQL/problems)."
      >
        <SecretInput
          isConfigured={(secureJsonFields && secureJsonFields.platformToken) as boolean}
          value={secureJsonData.platformToken || ''}
          placeholder="dt0s16.XXXXXXXXXXXXX.YYYYY..."
          width={60}
          onReset={onResetPlatformToken}
          onChange={onPlatformTokenChange}
        />
      </InlineField>

      <h3 className="page-heading">TLS/SSL Configuration</h3>

      <InlineField 
        label="Skip TLS Verify" 
        labelWidth={20}
        tooltip="Skip TLS certificate verification (insecure - use only for testing)"
      >
        <InlineSwitch
          value={jsonData.tlsSkipVerify || false}
          onChange={onTlsSkipVerifyChange}
        />
      </InlineField>

      {!jsonData.tlsSkipVerify && (
        <InlineField 
          label="TLS Certificate" 
          labelWidth={20}
          tooltip="TLS client certificate in PEM format (required when TLS verification is enabled)"
        >
          <div style={{ width: '500px' }}>
            <TextArea
              value={secureJsonData.tlsCertificate || ''}
              onChange={onTlsCertificateChange}
              placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              rows={8}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: '12px' }}
            />
            {(secureJsonFields && secureJsonFields.tlsCertificate) && (
              <div style={{ marginTop: '8px' }}>
                <span style={{ color: 'green', marginRight: '8px' }}>✓ Certificate configured</span>
                <button 
                  type="button" 
                  onClick={onResetTlsCertificate}
                  style={{ 
                    background: 'transparent', 
                    border: '1px solid #ccc', 
                    padding: '2px 8px',
                    cursor: 'pointer',
                    borderRadius: '3px'
                  }}
                >
                  Reset
                </button>
              </div>
            )}
          </div>
        </InlineField>
      )}
    </div>
  );
}
