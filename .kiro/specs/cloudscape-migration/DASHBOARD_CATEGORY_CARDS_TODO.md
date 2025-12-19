# Dashboard Category Cards - Implementation Plan

## Current Status
✅ KPI cards are clickable and working
✅ Service cards show category badges (clickable)
✅ Findings page has advanced filtering

## What's Missing
The legacy dashboard shows category breakdown cards (Security, Reliability, Cost Optimization, Performance Efficiency) with severity counts displayed as icons at the bottom of each card.

### Legacy Dashboard Structure:
```
┌─────────────────────────────────────────────────────────┐
│ Criticality Breakdown (Left)  │  Security Card (Right) │
│ ├─ High: 25 (10%)             │  ┌──────────────────┐  │
│ ├─ Medium: 86 (36%)           │  │ 178              │  │
│ ├─ Low: 97 (40%)              │  │ Security         │  │
│ └─ Informational: 34 (14%)    │  │                  │  │
│                                │  │ 🚫21 ⚠️69 👁️60 ℹ️28│  │
│                                │  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
┌──────────────┬──────────────┬──────────────┬──────────┐
│ Reliability  │ Cost Opt     │ Performance  │ Op Excel │
│ 9            │ 39           │ 15           │ X        │
│ 🚫4 ⚠️5 👁️0 ℹ️0│ 🚫0 ⚠️4 👁️32 ℹ️3│ 🚫0 ⚠️12 👁️3 ℹ️0│ ...      │
└──────────────┴──────────────┴──────────────┴──────────┘
```

## Implementation Steps

### 1. Add getCategoryStats() Function ✅
- Already added to `dataLoader.js`
- Returns array of categories with severity breakdown
- Format: `{ category, total, high, medium, low, informational }`

### 2. Create CategoryCard Component
Create a new component that displays:
- Category name (Security, Reliability, etc.)
- Total count
- Severity breakdown with icons at bottom
- Clickable to navigate to Findings page with category filter
- Color-coded based on category type

### 3. Update Dashboard Layout
- Add section for category cards after KPI cards
- Use Grid layout for responsive design
- Display Security card larger (featured)
- Display other categories in smaller cards below

### 4. Add Severity Breakdown Display
Each card should show at bottom:
- 🚫 High count (red)
- ⚠️ Medium count (orange)
- 👁️ Low count (blue)
- ℹ️ Informational count (grey)

### 5. Make Cards Clickable
- Click on card → Navigate to Findings page with category filter
- Click on severity icon → Navigate to Findings with category + severity filter

## Data Structure

```javascript
const categoryStats = [
  {
    category: 'Security',
    total: 178,
    high: 21,
    medium: 69,
    low: 60,
    informational: 28
  },
  {
    category: 'Reliability',
    total: 9,
    high: 4,
    medium: 5,
    low: 0,
    informational: 0
  },
  // ... more categories
];
```

## Color Mapping

- **Security**: Red (`bg-danger`)
- **Reliability**: Purple (`bg-fuchsia`)
- **Cost Optimization**: Blue (`bg-primary`)
- **Performance Efficiency**: Green (`bg-success`)
- **Operational Excellence**: Grey (`bg-secondary`)

## Next Steps

1. Create `CategoryCard.jsx` component
2. Update Dashboard to use `getCategoryStats()`
3. Add category cards section to Dashboard layout
4. Test clickability and navigation
5. Verify severity breakdowns are accurate

## Files to Modify

- ✅ `cloudscape-ui/src/utils/dataLoader.js` - Added getCategoryStats()
- ⏳ `cloudscape-ui/src/components/CategoryCard.jsx` - NEW
- ⏳ `cloudscape-ui/src/components/Dashboard.jsx` - Add category cards section
- ⏳ `cloudscape-ui/src/utils/formatters.js` - May need category color mapping

## Status
✅ **COMPLETE** - Category cards implemented with severity breakdown icons and clickable navigation
