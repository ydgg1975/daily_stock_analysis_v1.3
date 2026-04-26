"""
Unit tests for sector feature calculation.

Tests the sector.py module functions including:
- compute_sector_strength_score()
- compute_sector_persistence_score()
- classify_sector_state()
- compute_sector_features()
"""

import pytest
from src.market_diagnostic.data.models import SectorDailyData
from src.market_diagnostic.features.sector import (
    compute_sector_strength_score,
    compute_sector_persistence_score,
    classify_sector_state,
    compute_sector_features,
    compute_all_sector_features,
    SectorFeatureResult,
)


def create_test_sector(
    industry_code: str = "BK0447",
    industry_name: str = "电子",
    ret_1d: float = 0.02,
    ret_5d: float = 0.10,
    ret_20d: float = 0.25,
    excess_ret_1d: float = 0.01,
    breadth_20: float = 0.65,
    new_high_ratio: float = 0.15,
    amount: float = 500.0,
    amount_share: float = 0.08,
    amount_share_delta: float = 0.02,
    limit_up_count: int = 5,
    turnover: float = 0.03,
) -> SectorDailyData:
    """Helper to create test sector data."""
    return SectorDailyData(
        date="2024-01-15",
        industry_code=industry_code,
        industry_name=industry_name,
        ret_1d=ret_1d,
        ret_5d=ret_5d,
        ret_20d=ret_20d,
        excess_ret_1d=excess_ret_1d,
        breadth_20=breadth_20,
        new_high_ratio=new_high_ratio,
        amount=amount,
        amount_share=amount_share,
        amount_share_delta=amount_share_delta,
        limit_up_count=limit_up_count,
        turnover=turnover,
    )


class TestSectorStrengthScore:
    """Tests for compute_sector_strength_score()."""
    
    def test_single_sector_returns_zero(self):
        """Single sector should return 0 (no cross-sectional comparison)."""
        sector = create_test_sector()
        score = compute_sector_strength_score(sector, [sector])
        assert score == 0.0
    
    def test_empty_sectors_returns_zero(self):
        """Empty sector list should return 0."""
        sector = create_test_sector()
        score = compute_sector_strength_score(sector, [])
        assert score == 0.0
    
    def test_strong_sector_positive_score(self):
        """Sector with high returns and breadth should have positive score."""
        # Create a strong sector
        strong_sector = create_test_sector(
            ret_5d=0.20,
            ret_20d=0.40,
            breadth_20=0.80,
            new_high_ratio=0.25,
            amount_share_delta=0.05,
            limit_up_count=10,
        )
        
        # Create average sectors
        avg_sectors = [
            create_test_sector(
                industry_code=f"BK{i:04d}",
                ret_5d=0.05,
                ret_20d=0.10,
                breadth_20=0.50,
                new_high_ratio=0.05,
                amount_share_delta=0.0,
                limit_up_count=2,
            )
            for i in range(10)
        ]
        
        all_sectors = [strong_sector] + avg_sectors
        score = compute_sector_strength_score(strong_sector, all_sectors)
        
        # Strong sector should have positive score
        assert score > 0.5
    
    def test_weak_sector_negative_score(self):
        """Sector with low returns and breadth should have negative score."""
        # Create a weak sector
        weak_sector = create_test_sector(
            ret_5d=-0.10,
            ret_20d=-0.20,
            breadth_20=0.20,
            new_high_ratio=0.01,
            amount_share_delta=-0.03,
            limit_up_count=0,
        )
        
        # Create average sectors
        avg_sectors = [
            create_test_sector(
                industry_code=f"BK{i:04d}",
                ret_5d=0.05,
                ret_20d=0.10,
                breadth_20=0.50,
                new_high_ratio=0.05,
                amount_share_delta=0.0,
                limit_up_count=2,
            )
            for i in range(10)
        ]
        
        all_sectors = [weak_sector] + avg_sectors
        score = compute_sector_strength_score(weak_sector, all_sectors)
        
        # Weak sector should have negative score
        assert score < -0.5


class TestSectorPersistenceScore:
    """Tests for compute_sector_persistence_score()."""
    
    def test_no_historical_rankings_uses_returns(self):
        """Without historical rankings, should use return consistency."""
        sector = create_test_sector(ret_1d=0.02, ret_5d=0.10, ret_20d=0.25)
        score = compute_sector_persistence_score(sector)
        
        # All positive returns should give high persistence
        assert 0.8 <= score <= 1.0
    
    def test_mixed_returns_moderate_persistence(self):
        """Mixed positive/negative returns should give moderate persistence."""
        sector = create_test_sector(ret_1d=-0.01, ret_5d=0.05, ret_20d=0.15)
        score = compute_sector_persistence_score(sector)
        
        # Mixed returns should give moderate score
        assert 0.3 <= score <= 0.8
    
    def test_historical_rankings_top_5(self):
        """Consistent top-5 rankings should give high persistence."""
        sector = create_test_sector()
        rankings = [1, 2, 3, 2, 1]  # Consistently in top 5
        score = compute_sector_persistence_score(sector, rankings)
        
        # Top rankings should give high persistence
        assert score >= 0.8
    
    def test_historical_rankings_bottom(self):
        """Bottom rankings should give low persistence."""
        sector = create_test_sector()
        rankings = [28, 30, 29, 31, 27]  # Consistently at bottom
        score = compute_sector_persistence_score(sector, rankings)
        
        # Bottom rankings should give low persistence
        assert score <= 0.2


class TestClassifySectorState:
    """Tests for classify_sector_state()."""
    
    def test_main_uptrend_classification(self):
        """High strength and persistence should classify as 主升趋势."""
        state = classify_sector_state(
            strength_score=2.5,
            persistence_score=0.8,
            ret_20d=0.30
        )
        assert state == "主升趋势"
    
    def test_trend_strengthening_classification(self):
        """Moderate strength and persistence should classify as 趋势强化."""
        state = classify_sector_state(
            strength_score=1.8,
            persistence_score=0.5,
            ret_20d=0.15
        )
        assert state == "趋势强化"
    
    def test_consolidation_classification(self):
        """Low strength should classify as 震荡整理."""
        state = classify_sector_state(
            strength_score=0.3,
            persistence_score=0.4,
            ret_20d=0.05
        )
        assert state == "震荡整理"
    
    def test_oversold_bounce_classification(self):
        """Moderate strength with negative 20d return should classify as 超跌反弹."""
        state = classify_sector_state(
            strength_score=1.0,
            persistence_score=0.3,
            ret_20d=-0.15
        )
        assert state == "超跌反弹"
    
    def test_weak_fading_classification(self):
        """Negative strength should classify as 弱势退潮."""
        state = classify_sector_state(
            strength_score=-1.0,
            persistence_score=0.2,
            ret_20d=-0.10
        )
        assert state == "弱势退潮"


class TestComputeSectorFeatures:
    """Tests for compute_sector_features()."""
    
    def test_returns_sector_feature_result(self):
        """Should return SectorFeatureResult with all fields."""
        sector = create_test_sector()
        all_sectors = [sector] + [
            create_test_sector(industry_code=f"BK{i:04d}")
            for i in range(5)
        ]
        
        result = compute_sector_features(sector, all_sectors)
        
        assert isinstance(result, SectorFeatureResult)
        assert result.industry_code == "BK0447"
        assert result.industry_name == "电子"
        assert isinstance(result.strength_score, float)
        assert isinstance(result.persistence_score, float)
        assert isinstance(result.crowding_score, float)
        assert isinstance(result.leadership_score, float)
        assert result.state in [
            "主升趋势", "趋势强化", "震荡整理", "超跌反弹", "弱势退潮"
        ]
    
    def test_strong_sector_features(self):
        """Strong sector should have high scores and appropriate state."""
        strong_sector = create_test_sector(
            ret_5d=0.20,
            ret_20d=0.40,
            breadth_20=0.80,
            new_high_ratio=0.25,
            limit_up_count=10,
        )
        
        avg_sectors = [
            create_test_sector(
                industry_code=f"BK{i:04d}",
                ret_5d=0.05,
                ret_20d=0.10,
            )
            for i in range(10)
        ]
        
        all_sectors = [strong_sector] + avg_sectors
        result = compute_sector_features(strong_sector, all_sectors)
        
        # Strong sector should have positive strength score
        assert result.strength_score > 0
        # Should have high persistence (all positive returns)
        assert result.persistence_score > 0.7
        # Should be classified as strong state
        assert result.state in ["主升趋势", "趋势强化"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestComputeAllSectorFeatures:
    """Tests for compute_all_sector_features() parallel processing (Req 23.4)."""

    def _make_sectors(self, n: int) -> list:
        """Create n distinct test sectors."""
        return [
            create_test_sector(
                industry_code=f"BK{i:04d}",
                industry_name=f"行业{i}",
                ret_5d=0.01 * i,
                ret_20d=0.02 * i,
                breadth_20=min(0.9, 0.3 + 0.02 * i),
                limit_up_count=i % 5,
            )
            for i in range(n)
        ]

    def test_empty_input_returns_empty_list(self):
        """Empty sector list should return empty list."""
        assert compute_all_sector_features([]) == []

    def test_returns_same_count_as_input(self):
        """Output list length must equal input list length."""
        sectors = self._make_sectors(10)
        results = compute_all_sector_features(sectors)
        assert len(results) == 10

    def test_all_results_are_sector_feature_result(self):
        """Every element in the output must be a SectorFeatureResult."""
        sectors = self._make_sectors(5)
        results = compute_all_sector_features(sectors)
        for r in results:
            assert isinstance(r, SectorFeatureResult)

    def test_order_preserved(self):
        """Results must be in the same order as the input sectors."""
        sectors = self._make_sectors(8)
        results = compute_all_sector_features(sectors)
        for sector, result in zip(sectors, results):
            assert result.industry_code == sector.industry_code

    def test_parallel_matches_sequential(self):
        """Parallel results must match sequential compute_sector_features results."""
        sectors = self._make_sectors(12)
        parallel_results = compute_all_sector_features(sectors, max_workers=4)
        sequential_results = [compute_sector_features(s, sectors) for s in sectors]

        for par, seq in zip(parallel_results, sequential_results):
            assert par.industry_code == seq.industry_code
            assert abs(par.strength_score - seq.strength_score) < 1e-9
            assert abs(par.persistence_score - seq.persistence_score) < 1e-9
            assert par.state == seq.state

    def test_single_sector_works(self):
        """Single-sector input should work without errors."""
        sectors = self._make_sectors(1)
        results = compute_all_sector_features(sectors)
        assert len(results) == 1
        assert isinstance(results[0], SectorFeatureResult)

    def test_custom_max_workers(self):
        """Custom max_workers parameter should be accepted and produce correct results."""
        sectors = self._make_sectors(6)
        results_1 = compute_all_sector_features(sectors, max_workers=1)
        results_4 = compute_all_sector_features(sectors, max_workers=4)
        for r1, r4 in zip(results_1, results_4):
            assert r1.industry_code == r4.industry_code
            assert abs(r1.strength_score - r4.strength_score) < 1e-9

    def test_separate_cross_section_list(self):
        """Providing a separate all_sectors list should be used for Z-score calculation."""
        sectors = self._make_sectors(5)
        cross_section = self._make_sectors(20)  # Larger cross-section
        results = compute_all_sector_features(sectors, all_sectors=cross_section)
        assert len(results) == 5
        for r in results:
            assert isinstance(r, SectorFeatureResult)
