#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, logging
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

class RiskControls:
    def __init__(self, state_file=None):
        self.sf = state_file or PROJ/'data'/'risk_state.json'
        self._load()

    def _load(self):
        try:
            self.state = json.loads(self.sf.read_text()) if self.sf.exists() else {}
        except:
            self.state = {}
        self.state.setdefault('breaker', False)
        self.state.setdefault('consec', 0)
        self.state.setdefault('daily_pnl', 0.0)
        self.state.setdefault('max_dd', 0.0)

    def _save(self):
        self.sf.parent.mkdir(parents=True, exist_ok=True)
        self.sf.write_text(json.dumps(self.state, indent=2))

    def check(self, total_value, initial_capital):
        if self.state['breaker']:
            return {'pass': False, 'reason': '熔断已触发，需人工恢复'}
        pnl = (total_value - initial_capital) / initial_capital if initial_capital > 0 else 0
        self.state['daily_pnl'] = round(pnl, 4)
        dd = max(self.state.get('max_dd', 0), abs(min(0, pnl)))
        self.state['max_dd'] = round(dd, 4)
        self._save()
        if pnl < -0.03:
            self.state['breaker'] = True
            self._save()
            return {'pass': False, 'reason': f'日亏损{abs(pnl)*100:.1f}%，触发熔断'}
        if dd > 0.10:
            self.state['breaker'] = True
            self._save()
            return {'pass': False, 'reason': f'回撤{dd*100:.1f}%，触发熔断'}
        if self.state['consec'] >= 3:
            return {'pass': False, 'reason': f'连续{self.state["consec"]}次亏损，暂停交易'}
        return {'pass': True, 'reason': '', 'max_weight': 0.20}

    def record_trade(self, pnl_pct):
        self.state['consec'] = self.state['consec'] + 1 if pnl_pct < 0 else 0
        self._save()

    def reset(self):
        self.state = {'breaker': False, 'consec': 0, 'daily_pnl': 0.0, 'max_dd': 0.0}
        self._save()

    @property
    def status(self):
        if self.state['breaker']: return '熔断'
        if self.state['consec'] >= 2: return '预警'
        return '正常'

if __name__ == '__main__':
    rc = RiskControls()
    print(f'Status: {rc.status}')
    print(rc.check(1000000, 1000000))
