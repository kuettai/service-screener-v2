# Build Workflow Instructions

## Development Build Strategy

When working on this Service Screener project, use the appropriate build command based on the type of changes:

### Logging Feature

**All full scans now automatically generate timestamped log files:**
- **Log Location**: `logs/ssv2-YYYYMMDDHHMISS.log`
- **Content**: Complete console output including all print statements, warnings, and errors
- **Format**: Timestamped entries with both console display and file logging
- **Automatic**: No additional flags needed - logging is always enabled for full scans

**Example log filename**: `logs/ssv2-20250108143022.log` (January 8, 2025 at 14:30:22)

### UI-Related Changes (Cloudscape)
**Use: `./quick_rebuild.sh`**

For any changes to the Cloudscape UI components, React code, or frontend-related modifications:
- Component updates in `cloudscape-ui/src/components/`
- UI styling and layout changes
- Frontend data processing logic
- Chart and visualization updates

**Benefits:**
- Fast rebuild time (~10-15 seconds including fresh content enrichment)
- Generates fresh AWS content enrichment data (20+ relevant items)
- Perfect for rapid UI iteration with real content
- Automatically opens the updated HTML file
- **Uses existing backend data** (no AWS service scanning)

**Prerequisites:**
- Must have existing scan data from a previous full run with `--beta 1`
- Requires `ta.json`, `api-full.json`, and other backend-generated files

**Alternative: `./quick_rebuild_ui_only.sh`**
- Ultra-fast rebuild (~3 seconds)
- Uses existing content enrichment data
- Best for pure UI styling changes

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
- **Creates all required backend data files** (`ta.json`, `api-full.json`, etc.)

### Testing the New Cloudscape UI (Beta)
**Use `--beta 1` for testing the new UI:**

```bash
# UI Development (fast iteration with fresh content enrichment)
./quick_rebuild.sh

# UI Development (ultra-fast, existing content enrichment)
./quick_rebuild_ui_only.sh

# Performance Testing (concurrent mode is now default)
# Use --sequential if you need to test sequential execution
python3 main.py \
  --regions ap-southeast-1,us-east-1 \
  --services s3,cloudfront,ec2,rds,guardduty \
  --sequential 1 --beta 1 \
  --suppress_file ./suppressions.json

# For Fast testing, use minimal region and services
python3 main.py \
  --regions ap-southeast-1 \
  --services rds \
  --sequential 1 --beta 1
```

## Proper Development Workflow

### 1. Initial Setup (Required)
**Always start with a full scan to generate backend data:**

```bash
# Generate all backend data files (REQUIRED FIRST STEP)
python3 main.py \
  --regions ap-southeast-1,us-east-1 \
  --services s3,cloudfront,ec2,rds,guardduty \
  --beta 1 \
  --suppress_file ./suppressions.json
```

**What this creates:**
- `adminlte/aws/{account_id}/api-full.json` - Service scan results
- `adminlte/aws/{account_id}/ta.json` - Trusted Advisor data
- `adminlte/aws/{account_id}/index-legacy.html` - AdminLTE UI
- `adminlte/aws/{account_id}/index.html` - Cloudscape UI
- All CustomPage data files (COH, TA, etc.)

### 2. Frontend Development Iteration
**After initial setup, use quick rebuild for UI changes:**

```bash
# Fast UI iteration (uses existing backend data)
./quick_rebuild.sh
```

**What this does:**
- ✅ Rebuilds React Cloudscape UI components
- ✅ Generates fresh content enrichment data
- ✅ Uses existing `ta.json`, `api-full.json` from previous full scan
- ✅ Fast iteration cycle (~10-15 seconds)
- ❌ Does NOT regenerate backend service data
- ❌ Does NOT call AWS APIs

### 3. Backend Development
**When changing Python backend logic, run full scan:**

```bash
# Backend changes require full data regeneration
python3 main.py \
  --regions ap-southeast-1,us-east-1 \
  --services s3,cloudfront,ec2,rds,guardduty \
  --beta 1 \
  --suppress_file ./suppressions.json
```

## Architecture Separation

### Backend Data Generation (Python)
**Files:** `main.py`, `utils/OutputGenerator.py`, `services/*/`, `utils/CustomPage/`
**Responsibilities:**
- AWS API calls and data collection
- Service scanning and analysis
- Trusted Advisor data generation (`ta.json`)
- CustomPage data processing (COH, TA, etc.)
- JSON data file creation (`api-full.json`)

### Frontend UI Rebuilding (Cloudscape)
**Files:** `quick_rebuild.sh`, `cloudscape-ui/src/`
**Responsibilities:**
- React component compilation
- Content enrichment data refresh
- HTML generation with embedded data
- UI styling and interaction logic
- **Uses existing backend data files**

## Data Flow Architecture

```
Full Scan (--beta 1):
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AWS APIs      │───▶│  Python Backend  │───▶│  Backend Files  │
│ (Live Service   │    │  (main.py +      │    │  (ta.json,      │
│  Data)          │    │   OutputGen)     │    │   api-full.json)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                       ┌─────────────────┐    ┌──────────────────┐
                       │  Cloudscape UI  │◀───│  Data Embedding  │
                       │  (index.html)   │    │  (window.__*__)  │
                       └─────────────────┘    └──────────────────┘

Quick Rebuild:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Backend Files  │───▶│  Content Enrich  │───▶│  Cloudscape UI  │
│  (existing      │    │  + React Build   │    │  (updated       │
│   ta.json, etc.)│    │  (quick_rebuild) │    │   index.html)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Content Enrichment Features

The enhanced `./quick_rebuild.sh` now includes:
- ✅ **Fresh Content Fetching**: Pulls latest AWS blog posts and best practices
- ✅ **Smart Relevance Scoring**: Matches content to detected services (no more NaN%)
- ✅ **Enhanced AI/ML Topics**: Includes Bedrock, Agentic AI, QuickSuite, GenAI concepts
- ✅ **Collapsed Summary View**: Clean interface that expands on demand
- ✅ **Configurable Categories**: Security & Reliability, AI/ML & GenAI, Best Practices

## File Locations
- UI Components: `cloudscape-ui/src/components/`
- Core Engine: `services/*/` and `main.py`
- Quick Build Script (with content enrichment): `./quick_rebuild.sh`
- Quick Build Script (UI only): `./quick_rebuild_ui_only.sh`
- Generated Output (Cloudscape): `adminlte/aws/*/index.html`
- Generated Output (Legacy): `adminlte/aws/*/legacy/index.html`
- **Log Files**: `logs/ssv2-YYYYMMDDHHMISS.log`

## Log File Management

### Automatic Logging
- **Full Scans**: All output automatically logged to timestamped files
- **Quick Rebuilds**: Console output only (no log files generated)
- **Log Directory**: `logs/` (created automatically if doesn't exist)

### Log File Contents
- Complete console output with timestamps
- All print statements, warnings, and errors
- Service scan progress and timing information
- Framework generation status
- Build completion summary

### Log File Cleanup
```bash
# Remove logs older than 7 days
find logs/ -name "ssv2-*.log" -mtime +7 -delete

# Remove all log files
rm -f logs/ssv2-*.log

# Keep only the 10 most recent logs
ls -t logs/ssv2-*.log | tail -n +11 | xargs rm -f
```