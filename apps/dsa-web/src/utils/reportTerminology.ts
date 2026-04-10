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
  technicalscore: '技术分',
  fundamentalscore: '基本面分',
  sentimentscore: '情绪分',
  riskscore: '风险分',
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

const REPORT_HEADING_EN_MAP: Record<string, string> = {
  decisionsummary: 'Decision summary',
  executivesummary: 'Decision summary',
  executionplan: 'Execution plan',
  executionlayer: 'Execution plan',
  currentaction: 'Current action',
  immediateactions: 'Current action',
  fornewpositions: 'For new positions',
  newpositionplan: 'For new positions',
  forexistingpositions: 'For existing positions',
  conditionsriskcontrol: 'Conditions and risk control',
  conditionsandriskcontrol: 'Conditions and risk control',
  evidence: 'Evidence and data',
  evidencedata: 'Evidence and data',
  evidencelayer: 'Evidence and data',
  market: 'Market',
  marketdata: 'Market data',
  technical: 'Technical',
  technicaldata: 'Technical data',
  fundamental: 'Fundamental',
  fundamentaldata: 'Fundamental data',
  earnings: 'Earnings',
  earningsdata: 'Earnings data',
  earningsoutlook: 'Earnings outlook',
  riskscatalysts: 'Risks and catalysts',
  risksandcatalysts: 'Risks and catalysts',
  riskscatalystsandsentiment: 'Risks, catalysts, and sentiment',
  bullishfactors: 'Bullish factors',
  corebullishfactors: 'Core bullish factors',
  riskfactors: 'Risk factors',
  corerisks: 'Core risks',
  technicalscore: 'Technical score',
  fundamentalscore: 'Fundamental score',
  sentimentscore: 'Sentiment score',
  riskscore: 'Risk score',
  catalystswatchconditions: 'Catalysts and watch conditions',
  catalystsandwatchconditions: 'Catalysts and watch conditions',
  marketsentiment: 'Market sentiment',
  socialtone: 'Retail tone',
  socialattention: 'Attention',
  socialnarrative: 'Narrative focus',
  socialnarrativefocus: 'Narrative focus',
  narrativefocus: 'Narrative focus',
  coverageaudit: 'Coverage and audit',
  coverageandaudit: 'Coverage and audit',
  coveragemissingfieldsaudit: 'Coverage and missing-field audit',
  coveragemissingdataaudit: 'Coverage and missing-data audit',
  missingfieldaudit: 'Missing-field audit',
  missingfieldauditfulltruth: 'Missing-field audit (full scope)',
  bymissingcause: 'By missing cause',
  integratedunavailable: 'Integrated but unavailable',
  notintegratedyet: 'Not integrated yet',
  sourcenotprovided: 'Not provided by current source',
  notapplicable: 'Not applicable',
  integrationpriority: 'Integration priority',
  highprioritymissing: 'High-priority missing fields',
  highprioritymissingfields: 'High-priority missing fields',
  mediumprioritymissing: 'Medium-priority missing fields',
  mediumprioritymissingfields: 'Medium-priority missing fields',
  lowconditionalmissing: 'Low-priority / conditional missing fields',
  lowconditionalmissingfields: 'Low-priority / conditional missing fields',
  additionalmissingfields: 'Additional missing fields',
  appendix: 'Appendix',
  决策摘要: 'Decision summary',
  执行计划: 'Execution plan',
  当前动作: 'Current action',
  新开仓策略: 'For new positions',
  已持仓策略: 'For existing positions',
  条件与风控: 'Conditions and risk control',
  证据与数据: 'Evidence and data',
  行情数据: 'Market data',
  技术数据: 'Technical data',
  基本面数据: 'Fundamental data',
  财报数据: 'Earnings data',
  风险与催化: 'Risks and catalysts',
  风险催化与情绪: 'Risks, catalysts, and sentiment',
  风险催化和情绪: 'Risks, catalysts, and sentiment',
  市场情绪: 'Market sentiment',
  看多因素: 'Bullish factors',
  核心看多因素: 'Core bullish factors',
  风险因素: 'Risk factors',
  核心风险: 'Core risks',
  技术分: 'Technical score',
  基本面分: 'Fundamental score',
  情绪分: 'Sentiment score',
  风险分: 'Risk score',
  催化与观察条件: 'Catalysts and watch conditions',
  散户讨论: 'Retail tone',
  关注度: 'Attention',
  叙事焦点: 'Narrative focus',
  覆盖与审计: 'Coverage and audit',
  覆盖与缺失字段审计: 'Coverage and missing-field audit',
  覆盖与缺失数据审计: 'Coverage and missing-data audit',
  缺失字段审计: 'Missing-field audit',
  缺失字段审计完整口径: 'Missing-field audit (full scope)',
  按缺失原因: 'By missing cause',
  已接入但本次未返回: 'Integrated but unavailable',
  字段待接入: 'Not integrated yet',
  当前数据源未提供: 'Not provided by current source',
  不适用: 'Not applicable',
  接入优先级: 'Integration priority',
  高优先级缺失字段: 'High-priority missing fields',
  中优先级缺失字段: 'Medium-priority missing fields',
  低优先级条件性缺失: 'Low-priority / conditional missing fields',
  其他缺失字段: 'Additional missing fields',
  附录: 'Appendix',
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

type ControlledValueRule = {
  aliases: string[];
  zh: string;
  en: string;
  supportZh: string;
  supportEn: string;
};

export type ReportControlledValueProfile = {
  value: string;
  support?: string;
  matched: boolean;
};

const CONTROLLED_VALUE_RULES: ControlledValueRule[] = [
  {
    aliases: ['观望', 'watch', 'wait', 'waitforconfirmation', 'waitforpullback', 'waitforpullbackconfirmation', '等待', '等待确认', '等待回踩', '等待回踩确认', '继续观察', '继续观察买点', '谨慎观望', '以观望为主', '观望为主', '继续跟踪', 'watchandwait'],
    zh: '观望',
    en: 'Watch',
    supportZh: '等待确认',
    supportEn: 'Wait for confirmation',
  },
  {
    aliases: ['看空', 'bearish', 'bear', '偏空', 'downtrend', 'trenddown', 'trendweakening', '弱势', '短线偏弱', '短线震荡偏弱', '震荡偏弱', '趋势转弱'],
    zh: '看空',
    en: 'Bearish',
    supportZh: '动能偏弱',
    supportEn: 'Momentum weak',
  },
  {
    aliases: ['看多', 'bullish', 'bull', '偏强', 'uptrend', 'trendup', 'trendstrengthening', '强势', '短线偏强', '短线震荡偏强', '震荡偏强', '趋势转强'],
    zh: '看多',
    en: 'Bullish',
    supportZh: '趋势转强',
    supportEn: 'Trend strengthening',
  },
  {
    aliases: ['持有', 'hold', 'continueholding', '继续持有', '继续持仓', '保持仓位', '维持持有'],
    zh: '持有',
    en: 'Hold',
    supportZh: '维持仓位',
    supportEn: 'Maintain position',
  },
  {
    aliases: ['回踩买点', '回调买点', '等待回踩确认后分批试仓', '优先等待回踩ma20一带出现承接再考虑分批试仓'],
    zh: '回踩买点',
    en: 'Pullback entry',
    supportZh: '等待承接确认',
    supportEn: 'Wait for support confirmation',
  },
  {
    aliases: ['分批试仓'],
    zh: '分批试仓',
    en: 'Scale in',
    supportZh: '分批建立底仓',
    supportEn: 'Add in tranches',
  },
  {
    aliases: ['等待回踩后分两笔建立底仓'],
    zh: '等待回踩后分两笔建立底仓',
    en: 'Build an initial position in two tranches after the pullback',
    supportZh: '回踩后再建仓',
    supportEn: 'Wait for the pullback before building size',
  },
  {
    aliases: ['量价结构未破坏前继续跟踪'],
    zh: '量价结构未破坏前继续跟踪',
    en: 'Keep tracking while the price / volume structure remains intact',
    supportZh: '结构仍然有效',
    supportEn: 'Structure still intact',
  },
  {
    aliases: ['量价结构未破坏'],
    zh: '量价结构未破坏',
    en: 'Price / volume structure intact',
    supportZh: '结构仍然有效',
    supportEn: 'Structure still intact',
  },
  {
    aliases: ['若放量跌破支撑位需立即收缩仓位', '放量跌破支撑位则收缩仓位', '若放量跌破支撑位则收缩仓位'],
    zh: '若放量跌破支撑位需立即收缩仓位',
    en: 'Trim immediately if support breaks on volume',
    supportZh: '跌破后收缩仓位',
    supportEn: 'Reduce exposure on break',
  },
  {
    aliases: ['跌破最近支撑后做多结构被技术性否定', '跌破最近支撑后做多结构被技术性否定。'],
    zh: '跌破最近支撑后，做多结构被技术性否定。',
    en: 'A break of nearby support invalidates the bullish structure.',
    supportZh: '多头结构失效',
    supportEn: 'Bullish structure invalidated',
  },
  {
    aliases: ['优先锚定前高与更强压力位'],
    zh: '优先锚定前高与更强压力位。',
    en: 'Anchor the target to the prior high and the stronger resistance zone.',
    supportZh: '瞄准前高压力',
    supportEn: 'Use prior resistance as the guide',
  },
  {
    aliases: ['减仓', 'trim', 'reduce', 'reduceposition', 'derisk', 'de-risk', '降低仓位', '收缩仓位', '控制仓位'],
    zh: '减仓',
    en: 'Trim',
    supportZh: '降低风险',
    supportEn: 'Reduce exposure',
  },
  {
    aliases: ['增持', 'accumulate', 'add', 'addposition', '加仓', '顺势加仓', 'buildposition', 'build', '试仓', '开仓', '建仓'],
    zh: '增持',
    en: 'Accumulate',
    supportZh: '顺势加仓',
    supportEn: 'Add on strength',
  },
  {
    aliases: ['买入', 'buy', 'entry', 'enter', '择机买入', '逢低买入', '回踩买点', '回调买点', '突破买点', '买点', '入场', '试仓', '建仓'],
    zh: '买入',
    en: 'Buy',
    supportZh: '入场条件具备',
    supportEn: 'Setup ready',
  },
  {
    aliases: ['卖出', 'sell', 'exit', '离场', '止盈', 'takeprofit'],
    zh: '卖出',
    en: 'Sell',
    supportZh: '退出风险',
    supportEn: 'Risk off',
  },
  {
    aliases: ['中性', 'neutral', 'sideways', '震荡', '盘整', '横盘', 'range', 'rangebound', '横向震荡'],
    zh: '中性',
    en: 'Neutral',
    supportZh: '震荡整理',
    supportEn: 'Range-bound',
  },
  {
    aliases: ['高', '较高', 'high', 'highconfidence', 'highconviction'],
    zh: '高',
    en: 'High',
    supportZh: '置信度较高',
    supportEn: 'Higher confidence',
  },
  {
    aliases: ['中高', 'mediumhigh', 'medium-high', 'midhigh', 'highermedium'],
    zh: '中高',
    en: 'Medium-high',
    supportZh: '置信度偏高',
    supportEn: 'Moderately strong',
  },
  {
    aliases: ['中', 'medium', 'moderate'],
    zh: '中',
    en: 'Medium',
    supportZh: '置信度一般',
    supportEn: 'Moderate confidence',
  },
  {
    aliases: ['中低', 'mediumlow', 'medium-low'],
    zh: '中低',
    en: 'Medium-low',
    supportZh: '置信度偏低',
    supportEn: 'Slightly weak',
  },
  {
    aliases: ['低', 'low'],
    zh: '低',
    en: 'Low',
    supportZh: '置信度较低',
    supportEn: 'Lower confidence',
  },
];

const matchControlledValueRule = (value: string): ControlledValueRule | null => {
  const token = normalizeTerminologyToken(value);
  if (!token) {
    return null;
  }

  return CONTROLLED_VALUE_RULES.find((rule) => rule.aliases.includes(token)) || null;
};

export const getReportControlledValueProfile = (
  value: string | null | undefined,
  language: TermLanguage,
): ReportControlledValueProfile => {
  const raw = String(value || '').trim();
  if (!raw) {
    return {
      value: raw,
      matched: false,
    };
  }

  const rule = matchControlledValueRule(raw);
  if (!rule) {
    return {
      value: raw,
      matched: false,
    };
  }

  return {
    value: language === 'en' ? rule.en : rule.zh,
    support: language === 'en' ? rule.supportEn : rule.supportZh,
    matched: true,
  };
};

export const localizeReportControlledValue = (
  value: string | null | undefined,
  language: TermLanguage,
): string => getReportControlledValueProfile(value, language).value;

export const localizeReportHeadingLabel = (label: string, language: TermLanguage): string => {
  const raw = String(label || '').trim();
  if (!raw) {
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

  if (language === 'en') {
    return REPORT_HEADING_EN_MAP[token] || raw;
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
