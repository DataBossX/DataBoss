# Connectors

This directory is for future connectors to external data sources.

## Planned Connectors

- `county_records.py` - County recorder API integrations
- `arc_search.py` - ArcGIS / county GIS data
- `idoc.py` - State oil & gas commission data
- `manual_login_bridge.py` - Manual login assistance for restricted sources

## Current Status

Connectors are not yet implemented. The app currently works with uploaded files only.

For production use, implement connectors to:
1. Fetch lease records from county recorders
2. Pull ownership data from state O&G commissions
3. Retrieve address data from tax assessors
4. Access PLSS grid shapefiles for accurate coordinates

## Implementation Notes

When implementing connectors:
- Cache all fetched data in `db/local_cache.sqlite`
- Track source and fetch date for all data
- Implement retry logic for network failures
- Never store credentials in code (use environment variables)
- Log all API calls for debugging
