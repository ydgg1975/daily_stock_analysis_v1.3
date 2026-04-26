#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for AkShare breadth data interfaces (Task 2.1.1)

This script verifies the following AkShare interfaces:
- ak.stock_zt_pool_em() - limit-up stocks
- ak.stock_dt_pool_em() - limit-down stocks
- ak.stock_zh_a_spot_em() - market-wide statistics

Requirements: 1.3, 1.6
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_limit_up_pool(test_date: str = None) -> Dict[str, Any]:
    """
    Test ak.stock_zt_pool_em() for limit-up stocks
    
    Args:
        test_date: Date in format 'YYYYMMDD', defaults to yesterday
        
    Returns:
        Dict with test results and field mappings
    """
    import akshare as ak
    
    if test_date is None:
        # Use yesterday as default (markets closed today)
        yesterday = datetime.now() - timedelta(days=1)
        test_date = yesterday.strftime('%Y%m%d')
    
    logger.info(f"Testing ak.stock_zt_pool_em(date='{test_date}')...")
    
    try:
        start_time = time.time()
        df = ak.stock_zt_pool_em(date=test_date)
        elapsed = time.time() - start_time
        
        result = {
            'success': True,
            'api': 'ak.stock_zt_pool_em',
            'date': test_date,
            'elapsed_seconds': round(elapsed, 2),
            'row_count': len(df) if df is not None else 0,
            'columns': list(df.columns) if df is not None else [],
            'sample_data': df.head(3).to_dict('records') if df is not None and not df.empty else [],
            'data_types': df.dtypes.to_dict() if df is not None else {},
            'missing_values': df.isnull().sum().to_dict() if df is not None else {},
        }
        
        logger.info(f"✓ Limit-up pool: {result['row_count']} stocks, {elapsed:.2f}s")
        logger.info(f"  Columns: {result['columns']}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Limit-up pool failed: {e}")
        return {
            'success': False,
            'api': 'ak.stock_zt_pool_em',
            'date': test_date,
            'error': str(e),
        }


def test_limit_down_pool(test_date: str = None) -> Dict[str, Any]:
    """
    Test ak.stock_zt_pool_dtgc_em() for limit-down stocks
    
    Args:
        test_date: Date in format 'YYYYMMDD', defaults to yesterday
        
    Returns:
        Dict with test results and field mappings
    """
    import akshare as ak
    
    if test_date is None:
        yesterday = datetime.now() - timedelta(days=1)
        test_date = yesterday.strftime('%Y%m%d')
    
    logger.info(f"Testing ak.stock_zt_pool_dtgc_em(date='{test_date}')...")
    
    try:
        start_time = time.time()
        df = ak.stock_zt_pool_dtgc_em(date=test_date)
        elapsed = time.time() - start_time
        
        result = {
            'success': True,
            'api': 'ak.stock_zt_pool_dtgc_em',
            'date': test_date,
            'elapsed_seconds': round(elapsed, 2),
            'row_count': len(df) if df is not None else 0,
            'columns': list(df.columns) if df is not None else [],
            'sample_data': df.head(3).to_dict('records') if df is not None and not df.empty else [],
            'data_types': df.dtypes.to_dict() if df is not None else {},
            'missing_values': df.isnull().sum().to_dict() if df is not None else {},
        }
        
        logger.info(f"✓ Limit-down pool: {result['row_count']} stocks, {elapsed:.2f}s")
        logger.info(f"  Columns: {result['columns']}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Limit-down pool failed: {e}")
        return {
            'success': False,
            'api': 'ak.stock_zt_pool_dtgc_em',
            'date': test_date,
            'error': str(e),
        }


def test_market_spot() -> Dict[str, Any]:
    """
    Test ak.stock_zh_a_spot_em() for market-wide statistics
    
    Returns:
        Dict with test results and field mappings
    """
    import akshare as ak
    
    logger.info("Testing ak.stock_zh_a_spot_em()...")
    
    try:
        start_time = time.time()
        df = ak.stock_zh_a_spot_em()
        elapsed = time.time() - start_time
        
        # Verify expected fields
        expected_fields = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '量比', '换手率']
        missing_fields = [f for f in expected_fields if f not in df.columns]
        
        result = {
            'success': True,
            'api': 'ak.stock_zh_a_spot_em',
            'elapsed_seconds': round(elapsed, 2),
            'row_count': len(df) if df is not None else 0,
            'columns': list(df.columns) if df is not None else [],
            'expected_fields': expected_fields,
            'missing_fields': missing_fields,
            'sample_data': df.head(3).to_dict('records') if df is not None and not df.empty else [],
            'data_types': df.dtypes.to_dict() if df is not None else {},
            'missing_values': df.isnull().sum().to_dict() if df is not None else {},
        }
        
        logger.info(f"✓ Market spot: {result['row_count']} stocks, {elapsed:.2f}s")
        logger.info(f"  Columns: {len(result['columns'])} fields")
        if missing_fields:
            logger.warning(f"  Missing expected fields: {missing_fields}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Market spot failed: {e}")
        return {
            'success': False,
            'api': 'ak.stock_zh_a_spot_em',
            'error': str(e),
        }


def analyze_data_quality(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze data quality issues across all test results
    
    Args:
        results: Dict of test results keyed by test name
        
    Returns:
        Dict with quality analysis
    """
    quality_report = {
        'total_tests': len(results),
        'successful_tests': sum(1 for r in results.values() if r.get('success', False)),
        'failed_tests': sum(1 for r in results.values() if not r.get('success', False)),
        'issues': [],
    }
    
    for test_name, result in results.items():
        if not result.get('success', False):
            quality_report['issues'].append({
                'test': test_name,
                'type': 'api_failure',
                'error': result.get('error', 'Unknown error'),
            })
            continue
        
        # Check for missing values
        missing_vals = result.get('missing_values', {})
        if missing_vals:
            high_missing = {k: v for k, v in missing_vals.items() if v > 0}
            if high_missing:
                quality_report['issues'].append({
                    'test': test_name,
                    'type': 'missing_values',
                    'fields': high_missing,
                })
        
        # Check for missing expected fields
        missing_fields = result.get('missing_fields', [])
        if missing_fields:
            quality_report['issues'].append({
                'test': test_name,
                'type': 'missing_fields',
                'fields': missing_fields,
            })
    
    return quality_report


def main():
    """Run all breadth data interface tests"""
    logger.info("=" * 80)
    logger.info("AkShare Breadth Data Interface Validation (Task 2.1.1)")
    logger.info("=" * 80)
    
    # Use a recent trading date for testing
    # Note: You may need to adjust this to a valid trading date
    test_date = '20250423'
    
    results = {}
    
    # Test 1: Limit-up pool
    logger.info("\n[Test 1/3] Limit-up pool")
    results['limit_up'] = test_limit_up_pool(test_date)
    time.sleep(2)  # Rate limiting
    
    # Test 2: Limit-down pool
    logger.info("\n[Test 2/3] Limit-down pool")
    results['limit_down'] = test_limit_down_pool(test_date)
    time.sleep(2)  # Rate limiting
    
    # Test 3: Market-wide spot
    logger.info("\n[Test 3/3] Market-wide spot quotes")
    results['market_spot'] = test_market_spot()
    
    # Analyze data quality
    logger.info("\n" + "=" * 80)
    logger.info("Data Quality Analysis")
    logger.info("=" * 80)
    quality = analyze_data_quality(results)
    
    logger.info(f"\nTotal tests: {quality['total_tests']}")
    logger.info(f"Successful: {quality['successful_tests']}")
    logger.info(f"Failed: {quality['failed_tests']}")
    
    if quality['issues']:
        logger.warning(f"\nData quality issues found: {len(quality['issues'])}")
        for issue in quality['issues']:
            logger.warning(f"  - {issue['test']}: {issue['type']}")
            if 'error' in issue:
                logger.warning(f"    Error: {issue['error']}")
            if 'fields' in issue:
                logger.warning(f"    Fields: {issue['fields']}")
    else:
        logger.info("\n✓ No data quality issues detected")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Summary")
    logger.info("=" * 80)
    
    for test_name, result in results.items():
        if result.get('success', False):
            logger.info(f"✓ {test_name}: {result.get('row_count', 0)} rows, "
                       f"{result.get('elapsed_seconds', 0)}s")
        else:
            logger.error(f"✗ {test_name}: FAILED")
    
    logger.info("\n" + "=" * 80)
    logger.info("Field Mappings Documentation")
    logger.info("=" * 80)
    
    for test_name, result in results.items():
        if result.get('success', False) and result.get('columns'):
            logger.info(f"\n{result['api']}:")
            logger.info(f"  Columns: {', '.join(result['columns'])}")
            if result.get('sample_data'):
                logger.info(f"  Sample (first row): {result['sample_data'][0]}")
    
    return results, quality


if __name__ == '__main__':
    results, quality = main()
