<!--
For Chinese contributors: qingzhijieyongzhongwentianxie。
For English contributors: please fill in English. All fields marked (EN) accept English.
-->

## PR Type

- [ ] fix
- [ ] feat
- [ ] refactor
- [ ] docs
- [ ] chore
- [ ] test

## Background And Problem

qingmiaoshudangqianwenti、yingxiangfanweiyuchufachangjing。  
*(EN) Describe the problem, its impact, and what triggers it.*

## Scope Of Change

qingliechuben PR xiugaidemokuaihewenjianfanwei。  
*(EN) List the modules and files changed in this PR.*

## Issue Link

bixutianxieyixiazhiyi / Fill in one of:
- `Fixes #<issue_number>`
- `Refs #<issue_number>`
- wu Issue shishuomingyuanyinyuyanshoubiaozhun / If no issue, explain the motivation and acceptance criteria

## Verification Commands And Results

qingtianxienishijizhixingguodeminglingheguanjianjieguo（buyaozhixie"yiceshi"）。  
*(EN) Paste the commands you actually ran and their key output (don't just write "tested"):*

```bash
# example
./scripts/ci_gate.sh
python -m pytest -m "not network"
```

guanjianshuchu/jielun / Key output & conclusion:

## Compatibility And Risk

qingshuomingjianrongxingyingxiang、qianzaifengxian（ruwuqingxie `None`）。  
*(EN) Describe compatibility impact and potential risks (write `None` if not applicable).*

- ruoben PR xiugaidisanfangmoxing / API dejianrongyuyi、qingqiucanshu、luyouqianzhuihuo provider fallback，qingtigong**guanfanglaiyuanlianjiehuogonggao**，bingshuomingzheshichangqiyueshu、dangqianyunxingshiyueshuhaishilinshijianrongchuli。  
  *(EN) If this PR changes third-party model/API compatibility, request parameters, routing prefixes, or provider fallback behavior, include an **official source link or announcement** and clarify whether the rule is permanent, runtime-specific, or a temporary compatibility workaround.)*
- ruoben PR yilaitedingyunxingshi / suodingyilaichuangkou（liru LiteLLM banbenfanwei、OpenAI-compatible luyou、YAML alias xingwei），qingxiemingdangqianyanzhengguodejianrongfanweiyufugailujing。  
  *(EN) If this PR depends on a specific runtime or pinned dependency window (for example a LiteLLM version range, OpenAI-compatible routing, or YAML alias behavior), state the compatibility window you verified and which code paths were covered.)*
- ruoben PR chujiyunxingshipeizhibaocun、qingli、qianyihuohuitianluoji，qingmingqueshuomingjiupeizhishifouhuibeizidonggaixie、qingkong、qianyihuobaochibubian，yijiyonghuruhehuifuyuanxingwei。  
  *(EN) If this PR touches runtime config save/cleanup/migration/backfill logic, explicitly describe whether existing config is rewritten, cleared, migrated, or left intact, and how users can restore the previous behavior.)*

## Rollback Plan

qingzhishaoxieyijukezhixingdehuigunfangan（bitian）。  
*(EN) Provide at least one actionable rollback step (required).*

- ruguoshijianrongxingxiufu，morenyingxiechu**zuixiaohuigunfangshi**（liru `revert this PR`），bingshuomingshifouxuyaoewaihuigunpeizhihuoshujuqianyi。  
  *(EN) For compatibility fixes, include the **minimal rollback path** (for example `revert this PR`) and whether any additional config or data rollback is required.)*

## EXTRACT_PROMPT Change (if applicable)

ruoben PR xiugaile `src/services/image_stock_extractor.py` zhongde `EXTRACT_PROMPT`，qingzaicichuzhantiewanzhengbiangenghoude prompt。  
*If this PR changes `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, paste the full updated prompt here:*

<details>
<summary>zhankai / Expand: Full EXTRACT_PROMPT</summary>

```
(paste full prompt here)
```

</details>

## Checklist

- [ ] ben PR youmingquedongjiheyewujiazhi / This PR has a clear motivation and value
- [ ] yitigongkefuxiandeyanzhengminglingyujieguo / Reproducible verification commands and results are included
- [ ] yipinggujianrongxingyufengxian / Compatibility and risk have been assessed
- [ ] yitigonghuigunfangan / A rollback plan is provided
- [ ] ruoshejiyonghukejianbiangeng，yitongbugengxinxiangguanwendangyu `docs/CHANGELOG.md`；`README.md` jinzaishouyejixinxibianhuashigengxin，xijieyouxianxieru `docs/*.md` / If user-visible changes are included, relevant docs and `docs/CHANGELOG.md` are updated; `README.md` is updated only for homepage-level changes, with details kept in `docs/*.md`
