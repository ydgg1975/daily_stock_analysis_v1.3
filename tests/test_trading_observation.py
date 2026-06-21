from types import SimpleNamespace

from src.services.trading_observation import build_trading_observation_summary


def _result(
    code,
    score,
    decision,
    operation,
    *,
    volume_ratio=None,
    change_pct=None,
    price=None,
    support=None,
    resistance=None,
):
    dashboard = {
        "core_conclusion": {
            "one_sentence": f"{code} reason",
            "position_advice": {
                "no_position": "等回踩确认",
                "has_position": "跌破支撑减仓",
            },
        },
        "data_perspective": {
            "volume_analysis": {"volume_ratio": volume_ratio},
            "price_position": {
                "current_price": price,
                "support_level": support,
                "resistance_level": resistance,
            },
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "10.00",
                "stop_loss": "9.50",
                "take_profit": "12.00",
            }
        },
    }
    return SimpleNamespace(
        code=code,
        name=f"股票{code}",
        sentiment_score=score,
        decision_type=decision,
        operation_advice=operation,
        analysis_summary=f"{code} summary",
        dashboard=dashboard,
        change_pct=change_pct,
        current_price=price,
        trend_prediction="看多",
    )


def test_build_trading_observation_summary_core_lists():
    strong = _result("000001", 82, "buy", "买入观察", volume_ratio=2.0, change_pct=3.2, price=12, resistance=11)
    weak = _result("000002", 35, "sell", "卖出", volume_ratio=1.8, change_pct=-4.1, price=8, support=9)
    hold = _result("000003", 62, "hold", "持有观察")

    summary = build_trading_observation_summary([weak, strong, hold], top_n=1)

    assert summary["top_focus"][0]["name"] == "股票000001(000001)"
    assert summary["not_recommended"][0]["name"] == "股票000002(000002)"
    assert summary["tomorrow_watch"][0]["name"] == "股票000003(000003)"
    assert summary["volume_up"][0]["name"] == "股票000001(000001)"
    assert summary["volume_down"][0]["name"] == "股票000002(000002)"
    assert summary["breakout"][0]["name"] == "股票000001(000001)"
    assert summary["breakdown"][0]["name"] == "股票000002(000002)"
    assert "止损:9.50" in summary["trade_pool"][0]["battle_line"]
