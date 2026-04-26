# Market Diagnostic System Tests

This directory contains tests for the Market Diagnostic System.

## Test Files

### test_structure.py
Unit tests validating the project structure and data model definitions.

**Coverage:**
- Directory structure validation
- Configuration file validation
- Data model field validation
- Configuration threshold validation
- Regime strategy mapping validation

**Requirements Validated:** 1.1, 24.1, 24.2, 24.3, 25.1

### test_data_models_properties.py
Property-based tests using Hypothesis to validate data model correctness across a wide range of inputs.

**Coverage:**
- **Property 2: Data Structure Completeness** - Validates that MarketBreadthData contains all required fields with non-null values (Requirement 1.3)
- **Property 4: Capital Flow Data Structure** - Validates that CapitalFlowData contains all required fields (Requirement 1.5)
- Additional properties for IndexDailyData and SectorDailyData completeness
- Ratio field bounds validation (0-1 range)
- Count field non-negativity validation
- Amount field non-negativity validation

**Requirements Validated:** 1.3, 1.5

## Running Tests

### Run all tests:
```bash
python3 -m pytest src/market_diagnostic/tests/ -v
```

### Run specific test file:
```bash
python3 -m pytest src/market_diagnostic/tests/test_data_models_properties.py -v
```

### Run with coverage:
```bash
python3 -m pytest src/market_diagnostic/tests/ --cov=src.market_diagnostic.data.models
```

## Property-Based Testing

Property-based tests use the Hypothesis framework to automatically generate test cases. Each property test:

1. Defines a strategy for generating valid data model instances
2. Specifies a property that should hold for all generated instances
3. Runs 100+ test cases automatically (configurable)

### Benefits:
- Discovers edge cases that manual tests might miss
- Validates universal properties across the entire input space
- Provides stronger correctness guarantees than example-based tests

## Test Results

All tests pass successfully:
- 11 structure tests ✓
- 7 property tests ✓
- Total: 18 tests ✓

## Dependencies

- pytest >= 8.0.0
- hypothesis >= 6.0.0

Install with:
```bash
pip install -r requirements.txt
```
