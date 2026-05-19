# -*- coding: utf-8 -*-

"""Market strategy blueprints for CN/HK/US daily market recap."""



from dataclasses import dataclass

from typing import List





@dataclass(frozen=True)

class StrategyDimension:

    """Single strategy dimension used by market recap prompts."""



    name: str

    objective: str

    checkpoints: List[str]





@dataclass(frozen=True)

class MarketStrategyBlueprint:

    """Region specific market strategy blueprint."""



    region: str

    title: str

    positioning: str

    principles: List[str]

    dimensions: List[StrategyDimension]

    action_framework: List[str]



    def to_prompt_block(self) -> str:

        """Render blueprint as prompt instructions."""

        principles_text = "\n".join([f"- {item}" for item in self.principles])

        action_text = "\n".join([f"- {item}" for item in self.action_framework])



        dims = []

        for dim in self.dimensions:

            checkpoints = "\n".join([f"  - {cp}" for cp in dim.checkpoints])

            dims.append(f"- {dim.name}: {dim.objective}\n{checkpoints}")

        dimensions_text = "\n".join(dims)



        return (

            f"## Strategy Blueprint: {self.title}\n"

            f"{self.positioning}\n\n"

            f"### Strategy Principles\n{principles_text}\n\n"

            f"### Analysis Dimensions\n{dimensions_text}\n\n"

            f"### Action Framework\n{action_text}"

        )



    def to_markdown_block(self) -> str:

        """Render blueprint as markdown section for template fallback report."""

        dims = "\n".join([f"- **{dim.name}**: {dim.objective}" for dim in self.dimensions])

        section_title = "### VI. Strategy Framework" if self.region == "us" else "### 6. 전략 프레임워크"

        return f"{section_title}\n{dims}\n"





CN_BLUEPRINT = MarketStrategyBlueprint(
    region="cn",
    title="A주 시장 3단계 복기 전략",
    positioning="지수 추세, 자금 흐름, 섹터 순환을 함께 보고 다음 거래일 계획을 세웁니다.",
    principles=[
        "먼저 지수 방향을 보고, 다음으로 거래량 구조와 섹터 지속성을 확인합니다.",
        "결론은 반드시 포지션, 리듬, 리스크 통제 행동으로 연결합니다.",
        "당일 데이터와 최근 3일 뉴스를 기준으로 판단하고 검증되지 않은 정보는 배제합니다.",
    ],
    dimensions=[
        StrategyDimension(
            "지수",
            "상승/하락/횡보 방향과 변동성을 판정합니다.",
            ["주요 지수 방향 일치 여부", "거래량이 가격 흐름을 뒷받침하는지", "핵심 지지/저항 구간 변화"],
        ),
        StrategyDimension(
            "자금",
            "거래대금과 주도 업종의 수급을 확인합니다.",
            ["거래대금 증감", "상승/하락 종목 수", "주도 업종의 자금 집중도"],
        ),
        StrategyDimension(
            "섹터",
            "주도 섹터의 확산과 지속 가능성을 점검합니다.",
            ["상승 섹터 확산 여부", "하락 섹터 집중도", "주도 섹터의 연속성"],
        ),
        StrategyDimension(
            "계획",
            "다음 거래일의 관찰 조건과 대응을 정리합니다.",
            ["공격/균형/방어 구분", "관찰할 확인 신호", "판단이 틀렸을 때의 무효화 기준"],
        ),
    ],
    action_framework=[
        "공격: 지수와 주도 섹터가 함께 강화되고 거래대금이 뒷받침될 때.",
        "균형: 지수와 섹터 신호가 엇갈릴 때 포지션을 관리하며 확인을 기다립니다.",
        "방어: 지수 약화와 변동성 확대가 겹칠 때 손실 통제를 우선합니다.",
    ],
)

US_BLUEPRINT = MarketStrategyBlueprint(
    region="us",
    title="US Market Three-Step Review Strategy",
    positioning="Read index trend, macro flows, and sector rotation to form the next-session plan.",
    principles=[
        "Read market regime from S&P 500, Nasdaq, and Dow alignment first.",
        "Separate beta move from theme-driven alpha rotation.",
        "Translate recap into actionable risk-on/risk-off stance with clear invalidation points.",
    ],
    dimensions=[
        StrategyDimension(
            "Trend Regime",
            "Classify the market as momentum, range, or risk-off.",
            ["Index alignment", "Breadth and participation", "Volatility confirmation"],
        ),
        StrategyDimension(
            "Macro & Flows",
            "Map policy and rates narrative into equity risk appetite.",
            ["Rates and dollar direction", "Policy or earnings catalysts", "ETF and institutional flow clues"],
        ),
        StrategyDimension(
            "Sector Themes",
            "Identify persistent leaders and vulnerable laggards.",
            ["Leadership persistence", "Relative strength by sector", "Weak sectors that can spread risk"],
        ),
    ],
    action_framework=[
        "Risk-on: broad index breakout with expanding participation.",
        "Neutral: mixed index signals; focus on selective relative strength.",
        "Risk-off: failed breakouts and rising volatility; prioritize capital preservation.",
    ],
)

HK_BLUEPRINT = MarketStrategyBlueprint(
    region="hk",
    title="홍콩 시장 3단계 복기 전략",
    positioning="항셍 지수, 남향 자금, 섹터 순환을 함께 보고 다음 거래일 계획을 세웁니다.",
    principles=[
        "항셍/항셍테크/국유기업지수 방향을 먼저 확인합니다.",
        "남향 자금과 주도 섹터의 지속성을 함께 확인합니다.",
        "결론은 포지션, 리듬, 리스크 통제 행동으로 연결합니다.",
    ],
    dimensions=[
        StrategyDimension(
            "추세 구조",
            "시장이 상승, 횡보, 방어 국면 중 어디에 있는지 판정합니다.",
            ["항셍/항셍테크/국유기업지수 방향", "거래대금과 변동성", "주요 지지/저항 구간"],
        ),
        StrategyDimension(
            "자금 심리",
            "남향 자금과 환율, 정책 기대가 위험 선호에 주는 영향을 확인합니다.",
            ["남향 자금 유입/유출", "위안화와 달러 흐름", "정책 기대와 뉴스 촉매"],
        ),
        StrategyDimension(
            "주도 섹터",
            "기술, 플랫폼, 금융, 부동산 등 주요 섹터의 지속성을 점검합니다.",
            ["주도 섹터 연속성", "플랫폼/기술주 상대 강도", "금융/부동산 리스크 전이"],
        ),
    ],
    action_framework=[
        "공격: 지수 공진 상승, 남향 자금 유입, 주도 섹터 강화.",
        "균형: 지수 분화나 횡보, 포지션 관리와 확인 대기.",
        "방어: 지수 약화와 변동성 확대, 리스크 관리 우선.",
    ],
)





def get_market_strategy_blueprint(region: str) -> MarketStrategyBlueprint:

    """Return strategy blueprint by market region."""

    if region == "us":

        return US_BLUEPRINT

    if region == "hk":

        return HK_BLUEPRINT

    return CN_BLUEPRINT


