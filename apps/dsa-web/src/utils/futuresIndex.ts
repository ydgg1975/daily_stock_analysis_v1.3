import type { StockIndexItem } from '../types/stockIndex';

interface FuturesVariety {
  code: string;
  name: string;
  pinyinFull: string;
  pinyinAbbr: string;
  aliases?: string[];
  popularity: number;
}

const FUTURES_VARIETIES: FuturesVariety[] = [
  { code: 'RB', name: '螺纹钢', pinyinFull: 'luowengang', pinyinAbbr: 'lwg', aliases: ['螺纹'], popularity: 100 },
  { code: 'I', name: '铁矿石', pinyinFull: 'tiekuangshi', pinyinAbbr: 'tks', aliases: ['铁矿'], popularity: 98 },
  { code: 'JM', name: '焦煤', pinyinFull: 'jiaomei', pinyinAbbr: 'jm', aliases: ['炼焦煤'], popularity: 96 },
  { code: 'J', name: '焦炭', pinyinFull: 'jiaotan', pinyinAbbr: 'jt', popularity: 95 },
  { code: 'AU', name: '沪金', pinyinFull: 'hujin', pinyinAbbr: 'hj', aliases: ['黄金'], popularity: 94 },
  { code: 'AG', name: '沪银', pinyinFull: 'huyin', pinyinAbbr: 'hy', aliases: ['白银'], popularity: 93 },
  { code: 'CU', name: '沪铜', pinyinFull: 'hutong', pinyinAbbr: 'ht', aliases: ['铜'], popularity: 92 },
  { code: 'AL', name: '沪铝', pinyinFull: 'hulv', pinyinAbbr: 'hl', aliases: ['铝'], popularity: 88 },
  { code: 'ZN', name: '沪锌', pinyinFull: 'huxin', pinyinAbbr: 'hx', aliases: ['锌'], popularity: 87 },
  { code: 'NI', name: '沪镍', pinyinFull: 'huni', pinyinAbbr: 'hn', aliases: ['镍'], popularity: 86 },
  { code: 'SN', name: '沪锡', pinyinFull: 'huxi', pinyinAbbr: 'hx', aliases: ['锡'], popularity: 85 },
  { code: 'SS', name: '不锈钢', pinyinFull: 'buxiugang', pinyinAbbr: 'bxg', popularity: 84 },
  { code: 'FG', name: '玻璃', pinyinFull: 'boli', pinyinAbbr: 'bl', popularity: 83 },
  { code: 'SA', name: '纯碱', pinyinFull: 'chunjian', pinyinAbbr: 'cj', popularity: 82 },
  { code: 'MA', name: '甲醇', pinyinFull: 'jiachun', pinyinAbbr: 'jc', popularity: 81 },
  { code: 'M', name: '豆粕', pinyinFull: 'doupo', pinyinAbbr: 'dp', popularity: 80 },
  { code: 'RM', name: '菜粕', pinyinFull: 'caipo', pinyinAbbr: 'cp', popularity: 79 },
  { code: 'Y', name: '豆油', pinyinFull: 'douyou', pinyinAbbr: 'dy', popularity: 78 },
  { code: 'P', name: '棕榈油', pinyinFull: 'zonglvyou', pinyinAbbr: 'zly', popularity: 77 },
  { code: 'C', name: '玉米', pinyinFull: 'yumi', pinyinAbbr: 'ym', popularity: 76 },
  { code: 'CS', name: '淀粉', pinyinFull: 'dianfen', pinyinAbbr: 'df', aliases: ['玉米淀粉'], popularity: 75 },
  { code: 'SR', name: '白糖', pinyinFull: 'baitang', pinyinAbbr: 'bt', popularity: 74 },
  { code: 'CF', name: '棉花', pinyinFull: 'mianhua', pinyinAbbr: 'mh', popularity: 73 },
  { code: 'TA', name: 'PTA', pinyinFull: 'pta', pinyinAbbr: 'pta', popularity: 72 },
  { code: 'V', name: 'PVC', pinyinFull: 'pvc', pinyinAbbr: 'pvc', aliases: ['聚氯乙烯'], popularity: 71 },
  { code: 'L', name: '塑料', pinyinFull: 'suliao', pinyinAbbr: 'sl', popularity: 70 },
  { code: 'EG', name: '乙二醇', pinyinFull: 'yierchun', pinyinAbbr: 'yec', popularity: 69 },
  { code: 'SC', name: '原油', pinyinFull: 'yuanyou', pinyinAbbr: 'yy', popularity: 68 },
  { code: 'FU', name: '燃油', pinyinFull: 'ranyou', pinyinAbbr: 'ry', aliases: ['燃料油'], popularity: 67 },
  { code: 'LU', name: '低硫燃油', pinyinFull: 'diliuranyou', pinyinAbbr: 'dlry', popularity: 66 },
  { code: 'RU', name: '橡胶', pinyinFull: 'xiangjiao', pinyinAbbr: 'xj', aliases: ['天然橡胶'], popularity: 65 },
];

function formatContractMonth(year: number, month: number): string {
  return `${String(year % 100).padStart(2, '0')}${String(month).padStart(2, '0')}`;
}

function buildContractMonths(baseDate: Date): string[] {
  const months: string[] = [];
  const startYear = baseDate.getFullYear();
  const startMonth = baseDate.getMonth() + 1;

  for (let offset = -3; offset <= 36; offset += 1) {
    const zeroBased = startMonth - 1 + offset;
    const year = startYear + Math.floor(zeroBased / 12);
    const month = ((zeroBased % 12) + 12) % 12 + 1;
    months.push(formatContractMonth(year, month));
  }

  return months;
}

function buildItem(variety: FuturesVariety, code: string, name: string, popularity: number): StockIndexItem {
  return {
    canonicalCode: code,
    displayCode: code,
    nameZh: name,
    pinyinFull: variety.pinyinFull,
    pinyinAbbr: variety.pinyinAbbr,
    aliases: [
      variety.name,
      `${variety.name}${code.slice(variety.code.length)}`,
      ...(variety.aliases ?? []),
      ...(variety.aliases ?? []).map((alias) => `${alias}${code.slice(variety.code.length)}`),
    ],
    market: 'FUTURES',
    assetType: 'futures',
    active: true,
    popularity,
  };
}

export function buildFuturesIndex(baseDate = new Date()): StockIndexItem[] {
  const contractMonths = buildContractMonths(baseDate);
  const items: StockIndexItem[] = [];

  for (const variety of FUTURES_VARIETIES) {
    items.push(buildItem(variety, variety.code, `${variety.name}主力`, variety.popularity + 100));
    items.push(buildItem(variety, `${variety.code}0`, `${variety.name}主力连续`, variety.popularity + 90));
    for (const month of contractMonths) {
      items.push(buildItem(variety, `${variety.code}${month}`, `${variety.name}${month}`, variety.popularity));
    }
  }

  return items;
}
