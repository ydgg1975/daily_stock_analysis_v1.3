#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test AkShare interfaces for valuation and macro data

Task 2.1.3: Verify AkShare interfaces for valuation data
- Test `ak.stock_zh_index_value_csindex()` for index PE/PB
- Test `ak.bond_zh_us_rate()` for bond yields
- Test `ak.currency_boc_sina()` for exchange rates
- Document return formats and field mappings

Requirements: 1.6, 24.1
"""

import logging
import time
from typing import Dict, Any, Optional
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_index_valuation_csindex() -> Dict[str, Any]:
    """
    Test ak.stock_zh_index_value_csindex() for index PE/PB
    
    Returns:
        Dict containing test results and documentation
    """
    try:
        import akshare as ak
        
        logger.info("=" * 80)
        logger.info("Testing: ak.stock_zh_index_value_csindex()")
        logger.info("=" * 80)
        
        # Test with CSI300 (沪深300)
        symbol = "000300"
        logger.info(f"Fetching valuation data for index: {symbol}")
        
        start_time = time.time()
        df = ak.stock_zh_index_value_csindex(symbol=symbol)
        elapsed = time.time() - start_time
        
        logger.info(f"✓ API call successful (elapsed: {elapsed:.2f}s)")
        logger.info(f"✓ Returned {len(df)} rows")
        logger.info(f"✓ Columns: {list(df.columns)}")
        
        if not df.empty:
            logger.info(f"✓ Date range: {df.iloc[0]['日期']} to {df.iloc[-1]['日期']}")
            logger.info(f"\nSample data (latest 3 rows):")
            logger.info(f"\n{df.tail(3).to_string()}")
            
            # Document field mappings
            field_mapping = {
                '日期': 'date',
                '市盈率': 'pe_ratio',
                '市盈率TTM': 'pe_ttm',
                '市净率': 'pb_ratio',
                '股息率': 'dividend_yield',
            }
            
            logger.info(f"\nField mappings:")
            for cn, en in field_mapping.items():
                if cn in df.columns:
                    logger.info(f"  {cn} -> {en}")
        
        return {
            'success': True,
            'api': 'ak.stock_zh_index_value_csindex()',
            'symbol': symbol,
            'rows': len(df),
            'columns': list(df.columns),
            'elapsed': elapsed,
            'sample_data': df.tail(3).to_dict() if not df.empty else {},
            'field_mapping': field_mapping,
            'notes': 'Provides historical PE/PB/dividend yield for CSI indices'
        }
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        return {
            'success': False,
            'api': 'ak.stock_zh_index_value_csindex()',
            'error': str(e)
        }


def test_bond_yields() -> Dict[str, Any]:
    """
    Test ak.bond_zh_us_rate() for bond yields
    
    Returns:
        Dict containing test results and documentation
    """
    try:
        import akshare as ak
        
        logger.info("\n" + "=" * 80)
        logger.info("Testing: ak.bond_zh_us_rate()")
        logger.info("=" * 80)
        
        start_time = time.time()
        df = ak.bond_zh_us_rate()
        elapsed = time.time() - start_time
        
        logger.info(f"✓ API call successful (elapsed: {elapsed:.2f}s)")
        logger.info(f"✓ Returned {len(df)} rows")
        logger.info(f"✓ Columns: {list(df.columns)}")
        
        if not df.empty:
            logger.info(f"✓ Date range: {df.iloc[0]['日期']} to {df.iloc[-1]['日期']}")
            logger.info(f"\nSample data (latest 3 rows):")
            logger.info(f"\n{df.tail(3).to_string()}")
            
            # Document field mappings
            field_mapping = {
                '日期': 'date',
                '中国国债收益率10年': 'cn_10y',
                '中国国债收益率2年': 'cn_2y',
                '美国国债收益率10年': 'us_10y',
                '美国国债收益率2年': 'us_2y',
            }
            
            logger.info(f"\nField mappings:")
            for cn, en in field_mapping.items():
                if cn in df.columns:
                    logger.info(f"  {cn} -> {en}")
        
        return {
            'success': True,
            'api': 'ak.bond_zh_us_rate()',
            'rows': len(df),
            'columns': list(df.columns),
            'elapsed': elapsed,
            'sample_data': df.tail(3).to_dict() if not df.empty else {},
            'field_mapping': field_mapping,
            'notes': 'Provides China and US government bond yields (2Y, 10Y)'
        }
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        return {
            'success': False,
            'api': 'ak.bond_zh_us_rate()',
            'error': str(e)
        }


def test_exchange_rates() -> Dict[str, Any]:
    """
    Test ak.currency_boc_sina() for exchange rates
    
    Returns:
        Dict containing test results and documentation
    """
    try:
        import akshare as ak
        
        logger.info("\n" + "=" * 80)
        logger.info("Testing: ak.currency_boc_sina()")
        logger.info("=" * 80)
        
        start_time = time.time()
        df = ak.currency_boc_sina()
        elapsed = time.time() - start_time
        
        logger.info(f"✓ API call successful (elapsed: {elapsed:.2f}s)")
        logger.info(f"✓ Returned {len(df)} rows")
        logger.info(f"✓ Columns: {list(df.columns)}")
        
        if not df.empty:
            logger.info(f"\nSample data (first 5 rows):")
            logger.info(f"\n{df.head(5).to_string()}")
            
            # Document actual field mappings based on returned columns
            # The API returns time series data with date index
            field_mapping = {}
            for col in df.columns:
                if '日期' in col:
                    field_mapping[col] = 'date'
                elif '中行汇买价' in col:
                    field_mapping[col] = 'spot_buy'
                elif '中行钞买价' in col:
                    field_mapping[col] = 'cash_buy'
                elif '中行钞卖价' in col or '汇卖价' in col:
                    field_mapping[col] = 'spot_sell'
                elif '央行中间价' in col:
                    field_mapping[col] = 'central_parity'
                elif '中行折算价' in col:
                    field_mapping[col] = 'boc_conversion'
            
            logger.info(f"\nField mappings:")
            for cn, en in field_mapping.items():
                logger.info(f"  {cn} -> {en}")
            
            logger.info(f"\nNote: This API returns USD/CNY time series data")
        
        return {
            'success': True,
            'api': 'ak.currency_boc_sina()',
            'rows': len(df),
            'columns': list(df.columns),
            'elapsed': elapsed,
            'sample_data': df.head(5).to_dict() if not df.empty else {},
            'field_mapping': field_mapping,
            'notes': 'Provides Bank of China USD/CNY exchange rate time series'
        }
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        return {
            'success': False,
            'api': 'ak.currency_boc_sina()',
            'error': str(e)
        }


def test_index_valuation_hist() -> Dict[str, Any]:
    """
    Test historical valuation data availability
    
    Note: ak.stock_zh_index_value_hist_csindex() may not exist in all versions.
    The main API ak.stock_zh_index_value_csindex() already provides historical data.
    
    Returns:
        Dict containing test results and documentation
    """
    try:
        import akshare as ak
        
        logger.info("\n" + "=" * 80)
        logger.info("Testing: Historical valuation data availability")
        logger.info("=" * 80)
        
        # Check if the historical API exists
        if not hasattr(ak, 'stock_zh_index_value_hist_csindex'):
            logger.info("✓ Note: ak.stock_zh_index_value_hist_csindex() not available")
            logger.info("✓ Using ak.stock_zh_index_value_csindex() for historical data")
            
            # Test with CSI300 (沪深300)
            symbol = "000300"
            start_time = time.time()
            df = ak.stock_zh_index_value_csindex(symbol=symbol)
            elapsed = time.time() - start_time
            
            logger.info(f"✓ API call successful (elapsed: {elapsed:.2f}s)")
            logger.info(f"✓ Returned {len(df)} rows of historical data")
            
            return {
                'success': True,
                'api': 'ak.stock_zh_index_value_csindex() (for historical data)',
                'symbol': symbol,
                'rows': len(df),
                'columns': list(df.columns),
                'elapsed': elapsed,
                'notes': 'ak.stock_zh_index_value_csindex() provides sufficient historical data'
            }
        else:
            # If the API exists, test it
            symbol = "000300"
            start_time = time.time()
            df = ak.stock_zh_index_value_hist_csindex(symbol=symbol)
            elapsed = time.time() - start_time
            
            logger.info(f"✓ API call successful (elapsed: {elapsed:.2f}s)")
            logger.info(f"✓ Returned {len(df)} rows")
            
            return {
                'success': True,
                'api': 'ak.stock_zh_index_value_hist_csindex()',
                'symbol': symbol,
                'rows': len(df),
                'columns': list(df.columns),
                'elapsed': elapsed,
                'notes': 'Provides extended historical valuation data'
            }
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        return {
            'success': False,
            'api': 'Historical valuation data',
            'error': str(e)
        }


def main():
    """Run all valuation interface tests"""
    logger.info("Starting AkShare Valuation Interface Tests")
    logger.info("Task 2.1.3: Verify AkShare interfaces for valuation data")
    logger.info("")
    
    results = []
    
    # Test 1: Index valuation (current)
    results.append(test_index_valuation_csindex())
    time.sleep(2)  # Rate limiting
    
    # Test 2: Index valuation (historical)
    results.append(test_index_valuation_hist())
    time.sleep(2)  # Rate limiting
    
    # Test 3: Bond yields
    results.append(test_bond_yields())
    time.sleep(2)  # Rate limiting
    
    # Test 4: Exchange rates
    results.append(test_exchange_rates())
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    success_count = sum(1 for r in results if r.get('success', False))
    total_count = len(results)
    
    logger.info(f"Total tests: {total_count}")
    logger.info(f"Passed: {success_count}")
    logger.info(f"Failed: {total_count - success_count}")
    
    for result in results:
        status = "✓" if result.get('success', False) else "✗"
        api = result.get('api', 'Unknown')
        logger.info(f"{status} {api}")
        if not result.get('success', False):
            logger.info(f"  Error: {result.get('error', 'Unknown error')}")
    
    logger.info("\n" + "=" * 80)
    logger.info("DOCUMENTATION")
    logger.info("=" * 80)
    
    for result in results:
        if result.get('success', False):
            logger.info(f"\nAPI: {result.get('api')}")
            logger.info(f"Notes: {result.get('notes', 'N/A')}")
            if 'field_mapping' in result:
                logger.info("Field mappings:")
                for cn, en in result['field_mapping'].items():
                    logger.info(f"  {cn} -> {en}")
    
    return results


if __name__ == "__main__":
    main()
