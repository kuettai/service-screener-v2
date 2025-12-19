# Build Workflow Instructions

## Development Build Strategy

When working on this Service Screener project, use the appropriate build command based on the type of changes:

### UI-Related Changes
**Use: `./quick_rebuild.sh`**

For any changes to the Cloudscape UI components, React code, or frontend-related modifications:
- Component updates in `cloudscape-ui/src/components/`
- UI styling and layout changes
- Frontend data processing logic
- Chart and visualization updates

**Benefits:**
- Fast 3-second rebuild time
- Uses existing API data (no AWS calls)
- Perfect for rapid UI iteration
- Automatically opens the updated HTML file

### Core Engine Changes
**Use: ```python3 main.py \
  --regions ap-southeast-1,us-east-1 \
  --services s3,cloudfront,ec2,rds,guardduty \
  --beta 1 \
  --suppress_file ./suppressions.json
```**

For changes to the Python backend, data collection, or core service logic:
- Updates to service PageBuilders (e.g., `services/guardduty/GuarddutypageBuilder.py`)
- New service implementations
- Data processing logic changes
- API collection modifications

**Benefits:**
- Full data refresh from AWS APIs
- Tests the complete data pipeline
- Validates backend changes with real data
- Generates both API data and HTML output

## Quick Reference Commands

```bash
# UI Development (fast iteration)
./quick_rebuild.sh

# Core Engine Development (full pipeline)
python3 main.py \
  --regions ap-southeast-1,us-east-1 \
  --services s3,cloudfront,ec2,rds,guardduty \
  --beta 1 \
  --suppress_file ./suppressions.json
```

## File Locations
- UI Components: `cloudscape-ui/src/components/`
- Core Engine: `services/*/` and `main.py`
- Quick Build Script: `./quick_rebuild.sh`
- Generated Output: `adminlte/aws/*/index.html`