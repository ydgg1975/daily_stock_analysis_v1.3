const LEGACY_TEXT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/dapanfupan/g, '시장 리뷰'],
  [/Agudapanfupan/g, 'A주 시장 리뷰'],
  [/Agushichangfupan/g, 'A주 시장 리뷰'],
  [/Agu/g, 'A주'],
  [/meigu/g, '미국'],
  [/ganggu/g, '홍콩'],
  [/xiaofushangzhang/g, '소폭 상승'],
  [/qiangshishangzhang/g, '강한 상승'],
  [/xiaofuxiadie/g, '소폭 하락'],
  [/mingxianxiadie/g, '뚜렷한 하락'],
  [/zhendangzhengli/g, '박스권 등락'],
  [/viewfupan/g, '리뷰 확인'],
  [/ZH_NEUTRAL/g, '중립'],
  [/zhishu/g, '지수'],
  [/zuixin/g, '현재가'],
  [/zhangdiefu/g, '등락률'],
  [/kaipan/g, '시가'],
  [/zuigao/g, '고가'],
  [/zuidi/g, '저가'],
  [/zhenfu/g, '진폭'],
  [/chengjiaoe\(yi\)/g, '거래대금(억)'],
  [/chengjiaoe/g, '거래대금'],
  [/shangzhengzhishu/g, '상하이종합지수'],
  [/shenzhengchengzhi/g, '선전성분지수'],
  [/chuangyebanzhi/g, '창업판지수'],
  [/kechuang50/g, '커촹50'],
  [/shangzheng50/g, '상하이50'],
  [/hushen300/g, 'CSI300'],
];

export function localizeLegacyText(value?: string | null): string {
  let text = value ?? '';
  for (const [pattern, replacement] of LEGACY_TEXT_REPLACEMENTS) {
    text = text.replace(pattern, replacement);
  }
  return text;
}
