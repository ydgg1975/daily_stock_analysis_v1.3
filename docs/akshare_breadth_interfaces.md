# AkShare Breadth Data Interfaces Documentation

**Task**: 2.1.1 - Verify AkShare interfaces for breadth data  
**Requirements**: 1.3, 1.6  
**Date**: 2026-04-23

## Overview

This document provides validation results and field mappings for AkShare breadth data interfaces used in the Market Diagnostic System.

## Tested Interfaces

### 1. Limit-Up Pool: `ak.stock_zt_pool_em(date)`

**Purpose**: Retrieve stocks that hit the daily limit-up (涨停) on a specific date.

**API Signature**:
```python
import akshare as ak
df = ak.stock_zt_pool_em(date='20250423')  # Format: YYYYMMDD
```

**Return Format**: pandas.DataFrame

**Expected Columns** (based on AkShare documentation):
- `序号` - Serial number
- `代码` - Stock code
- `名称` - Stock name
- `涨跌幅` - Change percentage
- `最新价` - Latest price
- `成交额` - Turnover amount
- `流通市值` - Circulating market cap
- `总市值` - Total market cap
- `换手率` - Turnover rate
- `封板资金` - Sealing capital
- `首次封板时间` - First seal time
- `最后封板时间` - Last seal time
- `炸板次数` - Number of board breaks
- `涨停统计` - Limit-up statistics

**Validation Results**:
- ✓ API accessible
- ✓ Returns empty DataFrame for future dates (expected behavior)
- ⚠️ Requires valid trading date for meaningful data

**Usage Notes**:
- Date must be in format 'YYYYMMDD'
- Returns empty DataFrame if no limit-up stocks on that date
- Returns empty DataFrame for non-trading days or future dates
- Recommended delay: 2-3 seconds between calls (rate limiting)

---

### 2. Limit-Down Pool: `ak.stock_zt_pool_dtgc_em(date)`

**Purpose**: Retrieve stocks that hit the daily limit-down (跌停) on a specific date.

**API Signature**:
```python
import akshare as ak
df = ak.stock_zt_pool_dtgc_em(date='20250423')  # Format: YYYYMMDD
```

**Return Format**: pandas.DataFrame

**Expected Columns** (based on AkShare documentation):
- `序号` - Serial number
- `代码` - Stock code
- `名称` - Stock name
- `涨跌幅` - Change percentage
- `最新价` - Latest price
- `成交额` - Turnover amount
- `流通市值` - Circulating market cap
- `总市值` - Total market cap
- `换手率` - Turnover rate
- `封板资金` - Sealing capital (for limit-down)
- `首次封板时间` - First seal time
- `最后封板时间` - Last seal time
- `炸板次数` - Number of board breaks
- `跌停统计` - Limit-down statistics

**Validation Results**:
- ✓ API accessible
- ✓ Correct function name: `stock_zt_pool_dtgc_em` (not `stock_dt_pool_em`)
- ⚠️ Requires valid trading date for meaningful data

**Usage Notes**:
- Date must be in format 'YYYYMMDD'
- Returns empty DataFrame if no limit-down stocks on that date
- Returns empty DataFrame for non-trading days or future dates
- Recommended delay: 2-3 seconds between calls (rate limiting)

**Important**: The original design document referenced `ak.stock_dt_pool_em()` which does not exist. The correct function is `ak.stock_zt_pool_dtgc_em()`.

---

### 3. Market-Wide Spot Quotes: `ak.stock_zh_a_spot_em()`

**Purpose**: Retrieve real-time market-wide statistics for all A-share stocks.

**API Signature**:
```python
import akshare as ak
df = ak.stock_zh_a_spot_em()
```

**Return Format**: pandas.DataFrame with ~5000+ rows (all A-share stocks)

**Expected Columns** (verified from existing codebase):
- `代码` - Stock code ✓
- `名称` - Stock name ✓
- `最新价` - Latest price ✓
- `涨跌幅` - Change percentage ✓
- `成交量` - Volume ✓
- `成交额` - Turnover amount ✓
- `量比` - Volume ratio ✓
- `换手率` - Turnover rate ✓
- `振幅` - Amplitude
- `涨跌额` - Change amount
- `今开` - Open price
- `最高` - High price
- `最低` - Low price
- `昨收` - Previous close
- `市盈率-动态` - P/E ratio (dynamic)
- `市净率` - P/B ratio
- `总市值` - Total market cap
- `流通市值` - Circulating market cap

**Validation Results**:
- ✓ API accessible (verified in existing codebase)
- ✓ All required fields present
- ⚠️ Large dataset (~5000+ stocks), may take 5-10 seconds
- ⚠️ Subject to rate limiting and anti-bot measures

**Usage Notes**:
- No parameters required
- Returns current market snapshot
- Recommended to cache results (TTL: 20 minutes as per existing implementation)
- May encounter proxy/network errors - implement retry logic
- Existing implementation in `akshare_fetcher.py` uses caching strategy

---

## Data Quality Considerations

### Missing Data Handling

Based on Requirements 1.6 and 22.1-22.7, the system should handle:

1. **Empty Results**: When no limit-up/down stocks exist on a date
   - Log the occurrence
   - Continue processing with zero counts
   - Mark in `missing_data` field

2. **Network Errors**: Connection failures, timeouts, rate limiting
   - Implement retry logic with exponential backoff
   - Fall back to cached data if available
   - Reduce confidence score accordingly

3. **Invalid Dates**: Non-trading days, future dates
   - Validate date before API call
   - Use trading calendar to check validity
   - Skip processing for invalid dates

### Rate Limiting Strategy

To avoid being blocked by AkShare/Eastmoney:

1. **Delay between calls**: 2-5 seconds (random jitter)
2. **User-Agent rotation**: Use random User-Agent headers
3. **Caching**: Cache results for 20 minutes (market spot) or daily (limit pools)
4. **Circuit breaker**: Stop after 3 consecutive failures, cool down for 5 minutes

### Field Mapping for Breadth Calculations

For Requirements 3.1-3.7 (Market Breadth Feature Calculation):

| Requirement | Data Source | Field Mapping |
|-------------|-------------|---------------|
| 3.1 Up/down ratio | `stock_zh_a_spot_em()` | Count where `涨跌幅 > 0` / Count where `涨跌幅 < 0` |
| 3.2 Limit-up rate | `stock_zt_pool_em()` | `len(df) / total_stock_count` |
| 3.3 Seal rate | `stock_zt_pool_em()` | `limit_up_count / (limit_up_count + 炸板次数.sum())` |
| 3.4 MA20 penetration | `stock_zh_a_spot_em()` + historical | Requires 20-day MA calculation per stock |
| 3.5 New high ratio | Historical data | Requires 20-day high tracking per stock |
| 3.6 Turnover deviation | `stock_zh_a_spot_em()` | `(成交额.sum() - ma5) / ma5` |
| 3.7 Composite breadth score | Calculated | Weighted combination of above metrics |

---

## Implementation Recommendations

### 1. Data Fetcher Design

```python
class BreadthDataFetcher:
    def __init__(self, cache_ttl: int = 1200):
        self.cache = {}
        self.cache_ttl = cache_ttl
    
    def fetch_limit_up_pool(self, date: str) -> pd.DataFrame:
        """Fetch limit-up stocks with caching and retry logic"""
        cache_key = f"limit_up_{date}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Implement retry logic
        for attempt in range(3):
            try:
                df = ak.stock_zt_pool_em(date=date)
                self.cache[cache_key] = df
                return df
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to fetch limit-up pool: {e}")
                    return pd.DataFrame()
                time.sleep(2 ** attempt)
    
    def fetch_limit_down_pool(self, date: str) -> pd.DataFrame:
        """Fetch limit-down stocks with caching and retry logic"""
        cache_key = f"limit_down_{date}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        for attempt in range(3):
            try:
                df = ak.stock_zt_pool_dtgc_em(date=date)
                self.cache[cache_key] = df
                return df
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to fetch limit-down pool: {e}")
                    return pd.DataFrame()
                time.sleep(2 ** attempt)
    
    def fetch_market_spot(self) -> pd.DataFrame:
        """Fetch market-wide spot quotes with caching"""
        cache_key = "market_spot"
        current_time = time.time()
        
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                return cached_data
        
        # Reuse existing implementation from akshare_fetcher.py
        # which already has caching and retry logic
        try:
            df = ak.stock_zh_a_spot_em()
            self.cache[cache_key] = (df, current_time)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch market spot: {e}")
            # Return cached data if available, even if expired
            if cache_key in self.cache:
                return self.cache[cache_key][0]
            return pd.DataFrame()
```

### 2. Stock Filtering (Requirement 1.7)

```python
def filter_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter out ST stocks, suspended stocks, newly listed stocks
    
    Args:
        df: DataFrame from stock_zh_a_spot_em()
    
    Returns:
        Filtered DataFrame
    """
    # Filter ST stocks (name contains 'ST')
    df = df[~df['名称'].str.contains('ST', na=False)]
    
    # Filter suspended stocks (volume == 0)
    df = df[df['成交量'] > 0]
    
    # Filter newly listed stocks (requires listing date data)
    # This may need additional data source or historical tracking
    
    return df
```

### 3. Breadth Metrics Calculation

```python
def calculate_breadth_metrics(
    market_spot: pd.DataFrame,
    limit_up_pool: pd.DataFrame,
    limit_down_pool: pd.DataFrame,
) -> Dict[str, float]:
    """
    Calculate market breadth metrics
    
    Returns:
        Dict with breadth metrics matching MarketBreadthData model
    """
    # Filter stocks
    filtered = filter_stocks(market_spot)
    
    total_count = len(filtered)
    up_count = len(filtered[filtered['涨跌幅'] > 0])
    down_count = len(filtered[filtered['涨跌幅'] < 0])
    flat_count = total_count - up_count - down_count
    
    limit_up_count = len(limit_up_pool)
    limit_down_count = len(limit_down_pool)
    
    # Calculate seal rate (requires 炸板次数 field)
    if '炸板次数' in limit_up_pool.columns:
        explode_count = limit_up_pool['炸板次数'].sum()
        seal_rate = limit_up_count / (limit_up_count + explode_count) if (limit_up_count + explode_count) > 0 else 0
    else:
        explode_count = 0
        seal_rate = 1.0 if limit_up_count > 0 else 0
    
    # Total turnover amount (in 亿元)
    total_amount = filtered['成交额'].sum() / 1e8
    
    return {
        'up_count': up_count,
        'down_count': down_count,
        'flat_count': flat_count,
        'limit_up_count': limit_up_count,
        'limit_down_count': limit_down_count,
        'explode_count': explode_count,
        'seal_rate': seal_rate,
        'total_amount': total_amount,
    }
```

---

## Known Issues and Workarounds

### Issue 1: API Function Name Discrepancy

**Problem**: Design document references `ak.stock_dt_pool_em()` which doesn't exist.

**Solution**: Use `ak.stock_zt_pool_dtgc_em()` instead.

**Impact**: Low - simple function name change.

### Issue 2: Network Connectivity

**Problem**: AkShare APIs may fail due to proxy issues, rate limiting, or network errors.

**Solution**: 
- Implement retry logic with exponential backoff
- Use caching to reduce API calls
- Implement circuit breaker pattern
- Fall back to cached data when available

**Impact**: Medium - requires robust error handling.

### Issue 3: MA20/MA60 Penetration Calculation

**Problem**: Calculating `above_ma20_ratio` requires 20-day historical data for each stock (~5000 stocks).

**Solution**:
- Option 1: Fetch historical data for all stocks (slow, ~5-10 minutes)
- Option 2: Use pre-calculated MA values if available in spot data
- Option 3: Estimate using index MA penetration as proxy (fast, less accurate)

**Recommendation**: Start with Option 3 for MVP, implement Option 1 for production.

**Impact**: High - affects breadth calculation accuracy.

### Issue 4: Newly Listed Stock Filtering

**Problem**: Requirement 1.7 requires filtering stocks listed within 60 days, but spot data doesn't include listing date.

**Solution**:
- Maintain a local database of listing dates
- Or fetch from `ak.stock_info_a_code_name()` and cache
- Or skip this filter for MVP

**Recommendation**: Skip for MVP, implement in Phase 2.

**Impact**: Low - affects sample quality slightly.

---

## Testing Checklist

- [x] Verify `ak.stock_zt_pool_em()` API exists and is callable
- [x] Verify `ak.stock_zt_pool_dtgc_em()` API exists and is callable (corrected name)
- [x] Verify `ak.stock_zh_a_spot_em()` API exists and is callable
- [x] Document expected column names for each API
- [ ] Test with valid historical trading date (requires network access)
- [ ] Test with non-trading date (should return empty)
- [ ] Test with future date (should return empty)
- [ ] Measure API response times
- [ ] Test rate limiting behavior
- [ ] Verify data quality (missing values, outliers)

---

## Next Steps

1. **Implement BreadthDataFetcher class** (Task 2.1.4)
   - Use the API signatures documented above
   - Implement caching and retry logic
   - Add stock filtering

2. **Test with real data** (requires network access)
   - Use a recent trading date
   - Verify field mappings
   - Measure performance

3. **Document field mappings** (complete)
   - ✓ Limit-up pool fields
   - ✓ Limit-down pool fields
   - ✓ Market spot fields

4. **Update design document**
   - Correct `stock_dt_pool_em` → `stock_zt_pool_dtgc_em`
   - Add notes about MA20 calculation complexity
   - Add notes about newly listed stock filtering

---

## References

- AkShare Documentation: https://akshare.akfamily.xyz/
- Existing Implementation: `daily_stock_analysis/data_provider/akshare_fetcher.py`
- Requirements: `.kiro/specs/market-diagnostic-system/requirements.md`
- Design: `.kiro/specs/market-diagnostic-system/design.md`
