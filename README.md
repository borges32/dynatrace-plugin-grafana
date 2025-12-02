# Dynatrace Plugin for Grafana

A Grafana datasource plugin that enables communication with the Dynatrace Metrics V2 API. This plugin supports querying metrics with advanced filtering, transformations, custom time ranges, and alerting capabilities.

## Features

- **Dynatrace Metrics V2 API Integration**: Query metrics directly from Dynatrace using the latest API version
- **Advanced Metric Selectors**: Support for filters, transformations, splitBy, and sorting operations
- **Dimension Mapping**: Automatic label extraction from Dynatrace dimension maps for better metric visualization
- **Custom Time Ranges**: Use dashboard time ranges or define custom time periods
- **Flexible Resolution**: Configure data resolution (1m, 5m, 1h, etc.)
- **TLS Configuration**: Support for custom certificates and TLS verification options
- **Alerting Support**: Compatible with Grafana's alerting system

## Project Structure

```
dynatrace-plugin-grafana/
├── plugin/
│   └── opensource-dynatraceplugin-datasource/  # Main plugin directory
│       ├── src/                                 # Frontend source code (React/TypeScript)
│       ├── pkg/                                 # Backend source code (Go)
│       ├── dist/                                # Built plugin files
│       └── provisioning/                        # Grafana provisioning configs
└── simulator_metric_dynatrace/                  # Dynatrace API simulator for development
```

## Development Setup

### Prerequisites

- Node.js >= 18
- Go >= 1.19
- Docker and Docker Compose
- npm >= 10.8.2

### 1. Clone the Repository

```bash
git clone <repository-url>
cd dynatrace-plugin-grafana
```

### 2. Install Dependencies

```bash
cd plugin/opensource-dynatraceplugin-datasource
npm install
```

### 3. Start Development Environment

The project includes a Dynatrace API simulator for local development:

```bash
# Start the Dynatrace API simulator and Grafana
docker compose up -d
```

This will start:
- **Grafana**: Available at http://localhost:3000 (admin/admin)
- **Dynatrace API Simulator**: Available at http://localhost:8080

The simulator provides:
- Mock Dynatrace Metrics V2 API endpoints
- Pre-configured metrics (CPU usage, memory, response time, etc.)
- Support for metric selectors with filters and transformations
- Automatic dimension map generation

### 4. Build the Plugin

#### Development Mode

Build once and watch for changes:

```bash
npm run dev
```

This will:
1. Compile the Go backend to `dist/gpx_dynatrace_plugin_datasource_linux_amd64`
2. Watch and rebuild the frontend on file changes

#### Production Build

Build for production:

```bash
npm run build
```

This creates optimized builds for both frontend and backend.

### 5. Restart Grafana

After building, restart Grafana to load the updated plugin:

```bash
docker compose restart grafana
```

## Testing with the Simulator

### 1. Configure the Datasource

1. Open Grafana at http://localhost:3000
2. Go to **Configuration → Data Sources**
3. Click **Add data source**
4. Search for "Dynatrace Plugin Datasource"
5. Configure:
   - **API URL**: `http://dynatrace-api-simulator:8080`
   - **API Token**: `test-token`
   - **TLS Skip Verify**: Enabled (for development)

### 2. Example Queries

#### Simple Metric Query

```
builtin:host.cpu.usage
```

#### Query with Filters and Transformations

```
builtin:apps.other.crashCount.osAndVersion:filter(and(or(in("dt.entity.os",entitySelector("type(os)"))),or(in("dt.entity.device_application",entitySelector("type(mobile_application)"))))):splitBy():sort(value(auto,descending))
```

#### Available Simulator Metrics

- `builtin:host.cpu.usage`
- `builtin:host.mem.usage`
- `builtin:service.response.time`
- `builtin:service.request.count`
- `builtin:host.disk.avail`
- `builtin:apps.other.crashCount.osAndVersion`

### 3. Test API Directly

You can test the simulator API using curl:

```bash
# Health check
curl http://localhost:8080/health

# List all metrics
curl -H "Authorization: Api-Token test-token" \
  http://localhost:8080/api/v2/metrics

# Query specific metric
curl -H "Authorization: Api-Token test-token" \
  "http://localhost:8080/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage"
```

## How It Works

### Dimension Map to Labels

When Dynatrace API returns metrics with a `dimensionMap`, the plugin automatically:

1. **Extracts dimension values** from the API response
2. **Creates Grafana labels** using the dimension map key-value pairs
3. **Sets the field name** to the dimension values for cleaner legends
4. **Includes dimensions in the frame name** for better identification

Example API response:
```json
{
  "dimensionMap": {
    "dt.entity.device_application": "MOBILE_APPLICATION-1234567890ABCDEF"
  }
}
```

Results in:
- **Labels**: `dt.entity.device_application=MOBILE_APPLICATION-1234567890ABCDEF`
- **Legend**: `MOBILE_APPLICATION-1234567890ABCDEF`
- **Frame Name**: `builtin{dt.entity.device_application=MOBILE_APPLICATION-1234567890ABCDEF}`

## Configuration Options

### Datasource Configuration

- **API URL**: Base URL of your Dynatrace environment or simulator
- **API Token**: Dynatrace API token for authentication
- **TLS Skip Verify**: Skip TLS certificate verification (use only for development)
- **TLS Certificate**: Custom CA certificate (optional)

### Query Configuration

- **Metric Selector**: Dynatrace metric selector with optional filters and transformations
- **Use Dashboard Time**: Use Grafana dashboard time range
- **Custom Time Range**: Define specific start and end times
- **Resolution**: Data point resolution (e.g., 1m, 5m, 1h)

## Building for Production

### Build Plugin

```bash
npm run build
```

### Sign the Plugin (Optional)

If distributing the plugin:

```bash
npm run sign
```

### Package for Distribution

```bash
# Create a zip file with the dist directory
cd plugin/opensource-dynatraceplugin-datasource
zip -r dynatrace-plugin.zip dist/
```

## Deployment

### Install in Grafana

1. Copy the `dist` folder to your Grafana plugins directory:
   ```bash
   cp -r dist /var/lib/grafana/plugins/dynatrace-plugin
   ```

2. Restart Grafana:
   ```bash
   systemctl restart grafana-server
   ```

3. Enable the plugin in `grafana.ini`:
   ```ini
   [plugins]
   allow_loading_unsigned_plugins = opensource-dynatraceplugin-datasource
   ```

### Using with Real Dynatrace Environment

1. Generate an API token in Dynatrace with **Metrics read** permission
2. Configure the datasource with:
   - **API URL**: `https://your-environment.live.dynatrace.com`
   - **API Token**: Your generated token
   - **TLS Skip Verify**: Disabled (for production)

## Development Scripts

- `npm run build` - Build frontend and backend for production
- `npm run build:backend` - Build only the Go backend
- `npm run dev` - Build backend once and watch frontend
- `npm run test` - Run tests in watch mode
- `npm run test:ci` - Run tests once (CI mode)
- `npm run lint` - Lint code
- `npm run lint:fix` - Lint and fix issues
- `npm run typecheck` - Type check TypeScript
- `npm run sign` - Sign the plugin

## Troubleshooting

### Plugin not loading

1. Check Grafana logs: `docker logs opensource-dynatraceplugin-datasource`
2. Verify the backend binary exists: `ls -l dist/gpx_dynatrace_plugin_datasource_linux_amd64`
3. Ensure the plugin is unsigned or allowed: Check `grafana.ini`

### No data returned

1. Verify API connectivity: Test with curl
2. Check API token permissions
3. Verify metric selector syntax
4. Check Grafana query inspector for errors

### Backend changes not reflecting

1. Rebuild the backend: `npm run build:backend`
2. Restart Grafana: `docker compose restart grafana`
3. Check the binary timestamp: `ls -lh dist/gpx_dynatrace_plugin_datasource_linux_amd64`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with the simulator
5. Submit a pull request

## License

Apache-2.0

## Resources

- [Grafana Plugin Development](https://grafana.com/docs/grafana/latest/developers/plugins/)
- [Dynatrace Metrics V2 API](https://www.dynatrace.com/support/help/dynatrace-api/environment-api/metric-v2)
- [Grafana Data Source Plugin Guide](https://grafana.com/tutorials/build-a-data-source-plugin/)
