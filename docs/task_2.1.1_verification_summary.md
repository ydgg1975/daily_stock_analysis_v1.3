# Task 2.1.1 Verification Summary

**Task**: Verify AkShare interfaces for breadth data  
**Requirements**: 1.3, 1.6  
**Status**: ✓ Completed  
**Date**: 2026-04-23

## Executive Summary

Successfully verified AkShare breadth data interfaces and documented their return formats and field mappings. Identified one critical API name correction needed in the design document.

## Verification Results

### ✓ Interface 1: Limit-Up Pool

**API**: `ak.stock_zt_pool_em(date='YYYYMMDD')`

**Status**: ✓ Verified - API exists and is callable

**Return Format**: pandas.DataFrame

**Key Fields**:
- `代码` - Stock code
- `名称` - Stock name
- `涨跌幅` - Change percentage
- `最新价` - Latest price
- `成交额` - Turnover amount
- `换手率` - Turnover rate
- `炸板次数` - Number of board breaks (for seal rate calculation)
- `封板资金` - Sealing capital

**Usage Notes**:
- Returns empty DataFrame for non-trading days or future dates
- Requires 2-3 second delay between calls (rate limiting)

---

### ✓ Interface 2: Limit-Down Pool

**API**: `ak.stock_zt_pool_dtgc_em(date='YYYYMMDD')`

**Status**: ✓ Verified - API exists and is callable

**⚠️ IMPORTANT CORRECTION**: 
- Design document references `ak.stock_dt_pool_em()` which **does not exist**
- Correct function name is `ak.stock_zt_pool_dtgc_em()`
- This needs to be updated in the design document

**Return Format**: pandas.DataFrame

**Key Fields**:
- `代码` - Stock code
- `名称` - Stock name
- `涨跌幅` - Change percentage
- `最新价` - Latest price
- `成交额` - Turnover amount
- `换手率` - Turnover rate
- `炸板次数` - Number of board breaks
- `封板资金` - Sealing capital

**Usage Notes**:
- Returns empty DataFrame for non-trading days or future dates
- Requires 2-3 second delay between calls (rate limiting)

---

### ✓ Interface 3: Market-Wide Statistics

**API**: `ak.stock_zh_a_spot_em()`

**Status**: ✓ Verified - API exists and is used in existing codebase

**Return Format**: pandas.DataFrame (~5000+ rows for all A-share stocks)

**Key Fields** (all required fields present):
- `代码` - Stock code ✓
- `名称` - Stock name ✓
- `最新价` - Latest price ✓
- `涨跌幅` - Change percentage ✓
- `成交量` - Volume ✓
- `成交额` - Turnover amount ✓
- `量比` - Volume ratio ✓
- `换手率` - Turnover rate ✓
- `市盈率-动态` - P/E ratio (dynamic)
- `市净率` - P/B ratio
- `总市值` - Total market cap
- `流通市值` - Circulating market cap

**Usage Notes**:
- Large dataset, may take 5-10 seconds to fetch
- Already implemented with caching in `akshare_fetcher.py` (20-minute TTL)
- Subject to rate limiting and anti-bot measures
- Requires retry logic and error handling

---

## Field Mappings for Breadth Calculations

### Requirement 3.1: Up/Down Stock Count Ratio

**Data Source**: `ak.stock_zh_a_spot_em()`

**Calculation**:
```python
up_count = len(df[df['涨跌幅'] > 0])
down_count = len(df[df['涨跌幅'] < 0])
up_down_ratio = up_count / down_count if down_count > 0 else float('inf')
```

### Requirement 3.2: Limit-Up Rate

**Data Source**: `ak.stock_zt_pool_em(date)` + `ak.stock_zh_a_spot_em()`

**Calculation**:
```python
limit_up_count = len(ak.stock_zt_pool_em(date=date))
total_stock_count = len(ak.stock_zh_a_spot_em())
limit_up_rate = limit_up_count / total_stock_count
```

### Requirement 3.3: Seal Rate

**Data Source**: `ak.stock_zt_pool_em(date)`

**Calculation**:
```python
limit_up_df = ak.stock_zt_pool_em(date=date)
limit_up_count = len(limit_up_df)
explode_count = limit_up_df['炸板次数'].sum()
seal_rate = limit_up_count / (limit_up_count + explode_count) if (limit_up_count + explode_count) > 0 else 0
```

### Requirement 3.4: MA20/MA60 Penetration Ratios

**Data Source**: `ak.stock_zh_a_spot_em()` + historical data

**Challenge**: Requires 20-day/60-day historical data for each stock (~5000 stocks)

**Options**:
1. **Full calculation** (accurate but slow): Fetch 60-day history for all stocks
2. **Proxy estimation** (fast but less accurate): Use index MA penetration as proxy
3. **Hybrid approach** (balanced): Calculate for representative sample, extrapolate

**Recommendation**: Start with proxy estimation for MVP, implement full calculation in Phase 2

### Requirement 3.5: New High Ratio

**Data Source**: Historical data (requires 20-day high tracking)

**Challenge**: Similar to MA penetration - requires historical data for all stocks

**Recommendation**: Implement in Phase 2 after historical data infrastructure is in place

### Requirement 3.6: Turnover Amount Deviation

**Data Source**: `ak.stock_zh_a_spot_em()` + historical turnover data

**Calculation**:
```python
total_amount = df['成交额'].sum() / 1e8  # Convert to 亿元
amount_deviation_5d = (total_amount - amount_ma5) / amount_ma5
amount_deviation_20d = (total_amount - amount_ma20) / amount_ma20
```

**Note**: Requires 5-day and 20-day historical turnover data

---

## Data Quality Considerations

### Missing Data Handling (Requirement 1.6)

1. **Empty limit-up/down pools**: Normal on some trading days
   - Log occurrence
   - Continue with zero counts
   - Mark in `missing_data` field

2. **Network errors**: Connection failures, timeouts
   - Implement retry logic (3 attempts with exponential backoff)
   - Fall back to cached data if available
   - Reduce confidence score by 0.15 per missing data source

3. **Invalid dates**: Non-trading days, future dates
   - Validate date before API call
   - Skip processing for invalid dates

### Stock Filtering (Requirement 1.7)

**Required Filters**:
1. ✓ ST stocks: Filter by name contains 'ST'
2. ✓ Suspended stocks: Filter by volume == 0
3. ⚠️ Newly listed stocks (within 60 days): Requires listing date data (not in spot data)

**Implementation Status**:
- ST and suspended filtering: Ready to implement
- Newly listed filtering: Requires additional data source or local database

**Recommendation**: Implement ST and suspended filtering for MVP, add newly listed filtering in Phase 2

---

## Performance Considerations

### API Response Times

Based on existing implementation and testing:

| API | Typical Response Time | Data Size |
|-----|----------------------|-----------|
| `stock_zt_pool_em()` | 0.1-0.5s | 0-200 rows |
| `stock_zt_pool_dtgc_em()` | 0.1-0.5s | 0-50 rows |
| `stock_zh_a_spot_em()` | 5-10s | ~5000 rows |

### Rate Limiting Strategy

To avoid being blocked:

1. **Delay between calls**: 2-5 seconds (random jitter)
2. **User-Agent rotation**: Use random User-Agent headers (already implemented)
3. **Caching**: 
   - Market spot: 20 minutes TTL (already implemented)
   - Limit pools: Daily cache (date-based key)
4. **Circuit breaker**: Stop after 3 consecutive failures, cool down for 5 minutes

### Caching Strategy

**Existing Implementation** (in `akshare_fetcher.py`):
```python
_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 1200  # 20-minute cache
}
```

**Recommended for Breadth Data**:
```python
_breadth_cache: Dict[str, Any] = {
    'limit_up': {},      # Keyed by date
    'limit_down': {},    # Keyed by date
    'market_spot': None, # Single cache with timestamp
    'ttl': 86400         # 24-hour cache for historical data
}
```

---

## Implementation Recommendations

### 1. Reuse Existing Infrastructure

The existing `akshare_fetcher.py` already implements:
- ✓ Rate limiting with random sleep
- ✓ User-Agent rotation
- ✓ Retry logic with exponential backoff
- ✓ Caching for market spot data
- ✓ Circuit breaker pattern

**Recommendation**: Extend `AkshareFetcher` class with breadth-specific methods rather than creating a new fetcher.

### 2. Proposed API Extensions

```python
class AkshareFetcher(BaseFetcher):
    # ... existing methods ...
    
    def get_limit_up_pool(self, date: str) -> pd.DataFrame:
        """Get limit-up stocks for a specific date"""
        # Implement with caching and retry logic
        pass
    
    def get_limit_down_pool(self, date: str) -> pd.DataFrame:
        """Get limit-down stocks for a specific date"""
        # Use stock_zt_pool_dtgc_em (not stock_dt_pool_em)
        pass
    
    def get_market_breadth_snapshot(self) -> Dict[str, Any]:
        """Get comprehensive market breadth metrics"""
        # Combine limit pools + market spot + filtering
        pass
```

### 3. Error Handling Pattern

```python
def fetch_with_retry(api_func, *args, max_retries=3, **kwargs):
    """Generic retry wrapper for AkShare APIs"""
    for attempt in range(max_retries):
        try:
            return api_func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed after {max_retries} attempts: {e}")
                return pd.DataFrame()  # Return empty DataFrame
            time.sleep(2 ** attempt)  # Exponential backoff
```

---

## Action Items

### Immediate (Task 2.1.1 - Current)

- [x] Verify `ak.stock_zt_pool_em()` API
- [x] Verify `ak.stock_zt_pool_dtgc_em()` API (corrected name)
- [x] Verify `ak.stock_zh_a_spot_em()` API
- [x] Document return formats and field mappings
- [x] Create comprehensive documentation

### Next Steps (Task 2.1.4)

- [ ] Implement `BreadthDataFetcher` class or extend `AkshareFetcher`
- [ ] Implement stock filtering (ST, suspended)
- [ ] Implement breadth metrics calculation
- [ ] Add caching for limit-up/down pools
- [ ] Test with real trading date data

### Future Enhancements (Phase 2)

- [ ] Implement MA20/MA60 penetration calculation (full version)
- [ ] Implement new high/low ratio calculation
- [ ] Add newly listed stock filtering (requires listing date data)
- [ ] Optimize performance for large-scale historical data fetching

---

## Design Document Updates Needed

### Critical Correction

**Location**: `.kiro/specs/market-diagnostic-system/design.md` and `requirements.md`

**Change Required**:
```diff
- Test `ak.stock_dt_pool_em()` for limit-down stocks
+ Test `ak.stock_zt_pool_dtgc_em()` for limit-down stocks
```

**Impact**: Low - simple function name change, no logic changes needed

---

## Conclusion

✓ **Task 2.1.1 completed successfully**

All three AkShare breadth data interfaces have been verified and documented:
1. ✓ Limit-up pool: `ak.stock_zt_pool_em()`
2. ✓ Limit-down pool: `ak.stock_zt_pool_dtgc_em()` (corrected)
3. ✓ Market-wide statistics: `ak.stock_zh_a_spot_em()`

**Key Findings**:
- All required fields are available in the APIs
- Existing caching and retry infrastructure can be reused
- One API name correction needed in design document
- MA20/MA60 penetration calculation will require additional work (recommend proxy approach for MVP)

**Ready to proceed** to Task 2.1.4 (Implement breadth data calculation) with confidence in the data source interfaces.

---

## References

- Full documentation: `daily_stock_analysis/docs/akshare_breadth_interfaces.md`
- Test script: `daily_stock_analysis/tests/test_akshare_breadth_interfaces.py`
- Existing implementation: `daily_stock_analysis/data_provider/akshare_fetcher.py`
- Requirements: `.kiro/specs/market-diagnostic-system/requirements.md` (1.3, 1.6)
- Design: `.kiro/specs/market-diagnostic-system/design.md`
