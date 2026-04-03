const normalizeTerminologyToken = (value: string): string => value
  .toLowerCase()
  .replace(/[\s.,，。!！?？:：;；、()（）【】'"“”‘’`/|_%-]/g, '')
  .replace(/[[\]]/g, '')
  .trim();

type TermLanguage = 'zh' | 'en';

const REPORT_HEADING_ZH_MAP: Record<string, string> = {
  decisionsummary: '决策摘要',
  executivesummary: '决策摘要',
  executionplan: '执行计划',
  executionlayer: '执行计划',
  currentaction: '当前动作',
  immediateactions: '当前动作',
  fornewpositions: '新开仓策略',
  newpositionplan: '新开仓策略',
  forexistingpositions: '已持仓策略',
  conditionsriskcontrol: '条件与风控',
  conditionsandriskcontrol: '条件与风控',
  evidence: '证据与数据',
  evidencedata: '证据与数据',
  evidencelayer: '证据与数据',
  market: '市场',
  marketdata: '行情数据',
  technical: '技术面',
  technicaldata: '技术数据',
  fundamental: '基本面',
  fundamentaldata: '基本面数据',
  earnings: '财报',
  earningsdata: '财报数据',
  earningsoutlook: '业绩预期',
  riskscatalysts: '风险与催化',
  risksandcatalysts: '风险与催化',
  riskscatalystsandsentiment: '风险、催化与情绪',
  bullishfactors: '看多因素',
  corebullishfactors: '核心看多因素',
  riskfactors: '风险因素',
  corerisks: '核心风险',
  catalystswatchconditions: '催化与观察条件',
  catalystsandwatchconditions: '催化与观察条件',
  marketsentiment: '市场情绪',
  socialtone: '散户讨论',
  socialattention: '关注度',
  socialnarrative: '叙事焦点',
  socialnarrativefocus: '叙事焦点',
  narrativefocus: '叙事焦点',
  coverageaudit: '覆盖与审计',
  coverageandaudit: '覆盖与审计',
  coveragemissingfieldsaudit: '覆盖与缺失字段审计',
  coveragemissingdataaudit: '覆盖与缺失数据审计',
  missingfieldaudit: '缺失字段审计',
  missingfieldauditfulltruth: '缺失字段审计（完整口径）',
  bymissingcause: '按缺失原因',
  integratedunavailable: '已接入但本次未返回',
  notintegratedyet: '字段待接入',
  sourcenotprovided: '当前数据源未提供',
  notapplicable: '不适用',
  integrationpriority: '接入优先级',
  highprioritymissing: '高优先级缺失字段',
  highprioritymissingfields: '高优先级缺失字段',
  mediumprioritymissing: '中优先级缺失字段',
  mediumprioritymissingfields: '中优先级缺失字段',
  lowconditionalmissing: '低优先级/条件性缺失',
  lowconditionalmissingfields: '低优先级/条件性缺失',
  additionalmissingfields: '其他缺失字段',
  appendix: '附录',
};

const TERM_TRANSLATIONS: Record<TermLanguage, Record<string, string>> = {
  zh: {
    'report.analysisPrice': '分析价格',
    'chart.prevClose': '昨收',
    'chart.open': '开盘',
    'chart.high': '最高',
    'chart.low': '最低',
    'chart.change': '涨跌',
    'report.changePercent': '涨跌幅',
    'chart.volume': '成交量',
    'report.volumeRatio': '量比',
    'chart.turnover': '成交额',
    'report.turnoverRate': '换手率',
    'report.averagePrice': '均价',
    'report.vwap': '成交量加权均价（VWAP）',
    'report.earningsOutlook': '业绩预期',
    'report.retailTone': '散户讨论',
    'report.attention': '关注度',
    'report.narrativeFocus': '叙事焦点',
  },
  en: {
    'report.analysisPrice': 'Analysis price',
    'chart.prevClose': 'Prev close',
    'chart.open': 'Open',
    'chart.high': 'High',
    'chart.low': 'Low',
    'chart.change': 'Change',
    'report.changePercent': 'Change %',
    'chart.volume': 'Volume',
    'report.volumeRatio': 'Volume ratio',
    'chart.turnover': 'Turnover',
    'report.turnoverRate': 'Turnover rate',
    'report.averagePrice': 'Average price',
    'report.vwap': 'VWAP',
    'report.earningsOutlook': 'Earnings outlook',
    'report.retailTone': 'Retail tone',
    'report.attention': 'Attention',
    'report.narrativeFocus': 'Narrative focus',
  },
};

const termText = (language: TermLanguage, key: string): string => TERM_TRANSLATIONS[language][key] || key;

export const localizeReportHeadingLabel = (label: string, language: TermLanguage): string => {
  const raw = String(label || '').trim();
  if (!raw || language === 'en') {
    return raw;
  }

  const colonMatch = raw.match(/^([^:：]{1,120})([:：]\s*.*)$/);
  if (colonMatch?.[1] && colonMatch?.[2]) {
    const mapped = localizeReportHeadingLabel(colonMatch[1], language);
    if (mapped !== colonMatch[1]) {
      return `${mapped}${colonMatch[2]}`;
    }
  }

  const token = normalizeTerminologyToken(raw);
  if (!token) {
    return raw;
  }

  return REPORT_HEADING_ZH_MAP[token] || raw;
};

export const localizeReportTermLabel = (label: string, language: TermLanguage): string => {
  const raw = String(label || '').trim();
  if (!raw) {
    return raw;
  }

  const token = normalizeTerminologyToken(raw);
  if (!token) {
    return raw;
  }

  const hasPercent = /%/.test(raw);

  if (token.includes('analysisprice') || token === '分析价格') {
    return termText(language, 'report.analysisPrice');
  }
  if (token === 'prevclose' || token === 'previousclose' || token === '昨收' || token === '前收') {
    return termText(language, 'chart.prevClose');
  }
  if (token === 'sessionopen' || token === 'open' || token === '开盘') {
    return termText(language, 'chart.open');
  }
  if (token === 'sessionhigh' || token === 'high' || token === '最高') {
    return termText(language, 'chart.high');
  }
  if (token === 'sessionlow' || token === 'low' || token === '最低') {
    return termText(language, 'chart.low');
  }
  if (token === 'change' || token === '涨跌') {
    return hasPercent ? termText(language, 'report.changePercent') : termText(language, 'chart.change');
  }
  if (token === 'changepct' || token === 'changepercent' || token === '涨跌幅') {
    return termText(language, 'report.changePercent');
  }
  if (token === 'volume' || token === '成交量') {
    return termText(language, 'chart.volume');
  }
  if (token === 'volumeratio' || token === '量比') {
    return termText(language, 'report.volumeRatio');
  }
  if (token === 'turnover' || token === 'amount' || token === '成交额') {
    return termText(language, 'chart.turnover');
  }
  if (token === 'turnoverrate' || token === '换手率') {
    return termText(language, 'report.turnoverRate');
  }
  if (token === 'averageprice' || token === 'avgprice' || token === 'avgtradeprice' || token === '均价' || token === '平均价' || token === '成交均价') {
    return termText(language, 'report.averagePrice');
  }
  if (token === 'vwap') {
    return termText(language, 'report.vwap');
  }
  if (token === 'earningsoutlook' || token === '业绩预期') {
    return termText(language, 'report.earningsOutlook');
  }
  if (token === 'socialtone' || token === 'retailtone' || token === '情绪语气') {
    return termText(language, 'report.retailTone');
  }
  if (token === 'socialattention' || token === 'attention' || token === '关注度') {
    return termText(language, 'report.attention');
  }
  if (token === 'socialnarrativefocus' || token === 'narrativefocus' || token === '叙事焦点') {
    return termText(language, 'report.narrativeFocus');
  }

  return raw;
};
