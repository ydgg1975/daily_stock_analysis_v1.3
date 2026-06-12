# よくある質問（FAQ）

本ドキュメントは、ユーザーが遭遇しやすい問題とその解決策をまとめたものです。

---

## データ関連

### Q1: 米国株コード（例：AMD、AAPL）の分析時に価格が正しく表示されない？

**症状**: 米国株コードを入力した後、表示される価格が明らかに誤っている（例：AMD が 7.33 元と表示される）、または A 株として誤認識される。

**原因**: 旧バージョンのコードマッチングロジックが A 株のルールを優先していたため、コードの競合が発生していました。

**解決策**:
1. v2.3.0 で修正済み。システムは米国株コードの自動認識をサポートするようになりました
2. 問題が解消しない場合は、`.env` に以下を設定してください：
   ```bash
   YFINANCE_PRIORITY=0
   ```
   これにより、米国株データに対して Yahoo Finance データソースが優先されます

> 関連 Issue: [#153](https://github.com/ZhuLinsen/daily_stock_analysis/issues/153)

---

### Q2: レポート内で「出来高比率（Volume Ratio）」フィールドが空または N/A になる？

**症状**: 分析レポートで出来高比率のデータが欠落し、出来高変化に対する AI の判断に影響する。

**原因**: 一部のデフォルトのリアルタイム相場ソース（例：Sina インターフェース）は出来高比率フィールドを提供しません。

**解決策**:
1. v2.3.0 で修正済み。Tencent インターフェースが出来高比率の解析をサポートするようになりました
2. 推奨されるリアルタイム相場ソースの優先順位：
   ```bash
   REALTIME_SOURCE_PRIORITY=tencent,akshare_sina,efinance,akshare_em
   ```
3. システムにはフォールバックとして 5 日平均出来高の計算が組み込まれています

> 関連 Issue: [#155](https://github.com/ZhuLinsen/daily_stock_analysis/issues/155)

---

### Q3: Tushare のデータ取得に失敗し、Token エラーが表示される？

**症状**: ログに `Tushare data fetch failed: Your token is incorrect, please verify` と表示される

**解決策**:
1. **Tushare アカウントがない場合**: `TUSHARE_TOKEN` を設定する必要はありません。システムは自動的に無料のデータソース（AkShare、Efinance）を使用します
2. **Tushare アカウントがある場合**: Token が正しいか確認し、[Tushare Pro](https://tushare.pro/weborder/#/login?reg=834638) のパーソナルセンターで確認してください
3. 本プロジェクトのすべてのコア機能は Tushare なしでも正常に動作します

---

### Q4: データ取得がレート制限される、または空が返る？

**症状**: ログに `Circuit breaker triggered` と表示される、またはデータが `None` を返す

**原因**: 無料のデータソース（Eastmoney、Sina など）にはスクレイピング対策の仕組みがあり、高頻度のリクエストはレート制限を受けます。

**解決策**:
1. システムにはマルチソースの自動切り替えとサーキットブレーカー保護が組み込まれています
2. ウォッチリストのサイズを減らす、またはリクエスト間隔を広げる
3. 手動での分析トリガーを頻繁に行わないようにする

---

## 設定関連

### Q5: GitHub Actions の実行に失敗し、環境変数が見つからないと表示される？

**症状**: Actions のログに `GEMINI_API_KEY` または `STOCK_LIST` が undefined と表示される

**原因**: GitHub は `Secrets`（暗号化）と `Variables`（通常の変数）を区別しており、設定場所を誤ると読み取りに失敗します。

**解決策**:
1. リポジトリの `Settings` → `Secrets and variables` → `Actions` に移動
2. **Secrets**（`New repository secret` をクリック）: 機密情報を保存
   - `GEMINI_API_KEY`
   - `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - 各種 Webhook URL
3. **Variables**（`Variables` タブをクリック）: 非機密の設定を保存
   - `STOCK_LIST`
   - `GEMINI_MODEL`
   - `REPORT_TYPE`

---

### Q6: .env ファイルを変更しても設定が反映されない？

**解決策**:
1. `.env` ファイルがプロジェクトのルートディレクトリにあることを確認
2. **Docker デプロイ／WebUI 設定**:
   - `--env-file .env` / Compose の `env_file` は、ホストの `.env` を起動時の環境変数として注入するだけで、コンテナ内の `/app/.env` を作成したり書き戻したりはしません
   - 有効な `.env` ファイルにキーが含まれていない場合、WebUI 設定ページは起動時に注入された環境変数から同じキーをフォールバック表示します。`.env` の生のエクスポートには、依然として有効な設定ファイルの内容のみが含まれます
   - WebUI は `STOCK_LIST`、`SCHEDULE_ENABLED`、`SCHEDULE_TIME`、`SCHEDULE_RUN_IMMEDIATELY`、`RUN_IMMEDIATELY` をコンテナ内の `.env` に保存します
   - WebUI からの保存は現在のプロセスの設定リロードをトリガーし、ランタイムの読み取りは最新の永続化された `.env` から続行されます。例えば、定時実行は保存された `STOCK_LIST` をホットリロードし続けます
   - 同じキーを起動時環境変数として渡している場合（`--env-file .env`、`docker run -e ...`、または Compose の `environment:`）、その後の再起動では起動時の値が依然として優先されることがあります。WebUI で保存した `.env` の値を優先させたい場合は、同名のオーバーライドを更新または削除してください
   - WebUI で保存した設定を永続化するには、`ENV_FILE` を `/app/data/runtime.env` のような書き込み可能なデータボリューム上のファイルに向けてください。ホストの `.env` を単一ファイルとして `/app/.env` にバインドマウントしないでください
   - `SCHEDULE_*` と `RUN_IMMEDIATELY` は依然として**起動時のスケジューリング設定**です。これらを保存しても、すぐに分析実行がトリガーされたり、現在のプロセス内でスケジューラがホット再構築されたりはしません
   - スケジュール変更を現在のコンテナに反映させるには、コンテナを再起動し、プロセスがスケジュールモードで起動されていることを確認してください
3. **Docker での手動 `.env` 編集**: 変更後にコンテナを再起動
   ```bash
   docker-compose down && docker-compose up -d
   ```
4. **GitHub Actions**: `.env` ファイルは機能しません。必ず Secrets/Variables で設定してください
5. 複数の `.env` ファイル（例：`.env.local`）が上書きを引き起こしていないか確認

---

### Q7: Gemini/OpenAI API にアクセスするためのプロキシ設定方法は？

**解決策**:

`.env` に設定：
```bash
USE_PROXY=true
PROXY_HOST=127.0.0.1
PROXY_PORT=10809
```

> 注意: プロキシ設定はローカル実行時のみ有効です。GitHub Actions 環境ではプロキシは不要です。

---

### LLM 設定

> 詳細: [LLM 設定ガイド](LLM_CONFIG_GUIDE_EN.md)。

**Q: GEMINI_API_KEY と LLM_CHANNELS の両方を設定したのに、なぜ channels しか使われないのか？**

システムは優先順位に従って正確に 1 つのモードを使用します：高度な YAML ルーティング（`LITELLM_CONFIG`）＞ `LLM_CHANNELS` ＞ レガシーキー。ただし、YAML ルーティングはファイルが正常に解析でき、空でない `model_list` が得られる場合にのみ有効になります。YAML パスが無効、または内容が空の場合、システムは自動的に `LLM_CHANNELS` またはレガシーキーにフォールバックします。あるティアが有効になると、それより優先順位の低いティアは使用されません。

**Q: check_env で使用可能な AI モデルが設定されていないと表示される場合、どうすればよいか？**

まず 1 つのプロバイダーとその API キーから始めてください。プライマリモデルを固定したい場合は `LITELLM_MODEL=provider/model` を追加します。複数モデルの切り替えが必要な場合は、`LLM_CHANNELS` または高度な YAML ルーティングを設定します。`python scripts/check_env.py --config` で設定を検証し、`python scripts/check_env.py --llm` で実際に API を呼び出せます。

**Q: 複数のモデルを同時に使う方法は（例：AIHubmix + DeepSeek + Gemini）？**

チャネルモードを使用します：`LLM_CHANNELS=aihubmix,deepseek,gemini` を設定し、各チャネルの `LLM_{NAME}_BASE_URL`、`LLM_{NAME}_API_KEY`、`LLM_{NAME}_MODELS` を設定します。Web 設定 → AI モデル → AI モデルアクセスからビジュアルに設定することもできます。

**Q: 銘柄相談（ask-stock）／Agent ページで使用可能な LLM が設定されていないと表示されるが、レガシーの `GEMINI_*` / `OPENAI_*` / `ANTHROPIC_*` 設定しか使っていない。何を確認すべきか？**

まず `LITELLM_CONFIG` または `LLM_CHANNELS` が有効になっていないか確認してください。これらのティアはいずれもレガシーキーをオーバーライドします。どちらのティアも有効でなく、`AGENT_LITELLM_MODEL` が空の場合、銘柄相談 Agent は依然としてレガシープロバイダーのモデルを自動的に継承します：`GEMINI_MODEL`、`OPENAI_MODEL`、`ANTHROPIC_MODEL` は、対応するランタイム向けに LiteLLM のプロバイダープレフィックス付きモデル名にマッピングされます。この修正は古い設定を暗黙的に移行したりクリアしたりはしません。実際のバックエンドの理由をフロントエンドに返すだけなので、問題がキーの欠落なのか、モデル名の欠落なのか、上位ティアの設定が優先されているのかを確認できます。完全な互換性の詳細は [LLM 設定ガイド](LLM_CONFIG_GUIDE_EN.md) の「Ask-Stock Agent / LiteLLM compatibility notes」に記載されています。

---

## プッシュ通知関連

### Q8: ボットのプッシュに失敗し、メッセージが長すぎると表示される？

**症状**: 分析は成功したが通知が届かない。ログに 400 エラーまたは `Message too long` と表示される

**原因**: プラットフォームごとにメッセージ長の制限が異なります：
- WeChat Work: 4KB
- Feishu: 20KB
- DingTalk: 20KB

**解決策**:
1. **自動分割**: 最新バージョンでは長いメッセージの自動分割が実装されています
2. **単一銘柄プッシュモード**: `SINGLE_STOCK_NOTIFY=true` を設定すると、各銘柄の分析後すぐにプッシュします
3. **簡易レポート**: `REPORT_TYPE=simple` を設定すると簡略化されたフォーマットになります

---

### Q9: Telegram のプッシュメッセージが受信できない？

**解決策**:
1. `TELEGRAM_BOT_TOKEN` と `TELEGRAM_CHAT_ID` の両方が設定されていることを確認
2. Chat ID の取得方法：
   - Bot に任意のメッセージを送信
   - `https://api.telegram.org/bot<TOKEN>/getUpdates` にアクセス
   - 返された JSON 内で `chat.id` を探す
3. Bot が対象グループに追加されていることを確認（グループチャットの場合）
4. ローカルで実行する場合、Telegram API にアクセスできる必要があります（プロキシが必要な場合があります）

---

### Q10: WeChat Work の Markdown フォーマットが正しく表示されない？

**解決策**:
1. WeChat Work の Markdown サポートは限定的です。次の設定を試してください：
   ```bash
   WECHAT_MSG_TYPE=text
   ```
2. これによりプレーンテキスト形式のメッセージが送信されます

---

## AI モデル関連

### Q11: Gemini API が 429 エラー（リクエスト過多）を返す？

**症状**: ログに `Resource has been exhausted` または `429 Too Many Requests` と表示される

**解決策**:
1. Gemini の無料ティアにはレート制限があります（約 15 RPM）
2. 同時に分析する銘柄数を減らす
3. リクエスト遅延を増やす：
   ```bash
   GEMINI_REQUEST_DELAY=5
   ANALYSIS_DELAY=10
   ```
4. または、バックアップとして OpenAI 互換 API に切り替える

---

### Q12: DeepSeek などの中国語モデルを使う方法は？

**設定方法**:

```bash
# GEMINI_API_KEY を設定する必要はありません
OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
# deepseek-chat / deepseek-reasoner も引き続き互換ですが、DeepSeek は 2026/07/24 以降にこれらを非推奨としています
```

サポートされているモデルサービス：
- DeepSeek: `https://api.deepseek.com`
- Qwen（通義千問）: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Moonshot: `https://api.moonshot.cn/v1`

---

### Q12b: Ollama ローカルモデルを使う方法は？

**設定**: `OLLAMA_API_BASE` + `LITELLM_MODEL` を使用するか、チャネルモード（`LLM_CHANNELS=ollama` + `LLM_OLLAMA_BASE_URL` + `LLM_OLLAMA_MODELS`）を使用します。

**落とし穴**: Ollama に `OPENAI_BASE_URL` を使用しないでください。さもないとシステムが URL を誤って連結します（例：404、`api/generate/api/show`）。[LLM 設定ガイド](LLM_CONFIG_GUIDE_EN.md) の Example 4 とチャネルの例を参照してください。

---

### Q12c: `OllamaException / APIConnectionError`（All LLM models failed）が出る？

**症状**: ログに `litellm.APIConnectionError: OllamaException` または `Analysis failed: All LLM models failed (tried 1 model(s))` と表示される。

以下の 5 つのチェックポイントを順番に確認してください：

1. **Ollama サービスは起動しているか？**
   ```bash
   # プロセスを確認
   pgrep -a ollama
   # 出力がない場合は、まず起動する
   ollama serve
   ```
   リッスンしているか確認：`curl http://localhost:11434` は `Ollama is running` を返すはずです。

2. **`OLLAMA_API_BASE` は正しく設定されているか？**
   - ✅ 正しい: `OLLAMA_API_BASE=http://localhost:11434`
   - ❌ 誤り: Ollama のアドレスを `OPENAI_BASE_URL` に入れると、URL パスが壊れます（例：`…/api/generate/api/show`）。

3. **モデル名に `ollama/` プレフィックスが含まれているか？**
   - ✅ 正しい: `LITELLM_MODEL=ollama/qwen3:8b`
   - ❌ 誤り: `LITELLM_MODEL=qwen3:8b`（プレフィックスがない — litellm が Ollama にルーティングできません）

4. **モデルはローカルに pull されているか？**
   ```bash
   ollama list           # ダウンロード済みのモデルを一覧表示
   ollama pull qwen3:8b  # ない場合は pull する
   ```

5. **リモートまたは Docker デプロイのネットワーク／ファイアウォール**
   - Ollama が別のホストで動作している場合は、`OLLAMA_API_BASE` を実際の IP に設定してください（例：`http://192.168.1.100:11434`）。
   - ポート 11434 が開いており、Ollama が正しいアドレスにバインドされていることを確認してください（`OLLAMA_HOST=0.0.0.0:11434`）。

> 完全な設定例は [LLM 設定ガイド → Example 4 (Ollama)](LLM_CONFIG_GUIDE_EN.md#example-4-ollama) を参照してください。

---

## Docker 関連

### Q13: Docker コンテナが起動直後にすぐ終了する？

**解決策**:
1. コンテナのログを確認：
   ```bash
   docker logs <container_id>
   ```
2. よくある原因：
   - 環境変数が正しく設定されていない
   - `.env` ファイルのフォーマットエラー（例：余分なスペース）
   - 依存パッケージのバージョン競合

---

### Q14: Docker で API サービスにアクセスできない？

**解決策**:
1. 起動コマンドに `--host 0.0.0.0` が含まれていることを確認（127.0.0.1 ではいけません）
2. ポートマッピングが正しいか確認：
   ```yaml
    ports:
      - "8000:8000"
    ```

---

### Q14.1: Docker でインストールした場合、ソフトウェアのバージョンはどこに保存されるか？

**簡潔な答え**: Docker ユーザーにとって、信頼できるバージョンは Python ソースファイル内のハードコードされた定数ではなく、**実際にデプロイしたイメージタグ**です。

**理由**:
1. Docker の公開は `.github/workflows/docker-publish.yml` によって駆動され、`v*.*.*` に一致する Git タグ（例：`v3.12.0`）に対してのみリリースイメージを公開します。
2. そのため、Docker イメージのバージョンは `main.py`、`server.py`、その他のバックエンドモジュール内の固定値ではなく、**GitHub Release / Git タグ**に従います。
3. `apps/dsa-web/package.json` の `version` フィールドは現在プレースホルダーの `0.0.0` です。WebUI のバージョン／ビルドカードはフロントエンドアセットが再ビルドされたかどうかを確認するのに便利ですが、Docker のリリースバージョンではありません。
4. デスクトップアプリは `apps/dsa-desktop/package.json` に独自のバージョンを持ちますが、これは Electron デスクトップビルドにのみ適用され、Docker イメージには適用されません。

**現在の Docker バージョンを確認する方法**:
1. **デプロイコマンドまたは Compose ファイル内のイメージタグを確認**。例えば `ghcr.io/zhulinsen/daily_stock_analysis:v3.12.0` の場合、デプロイされたバージョンは `v3.12.0` です。
2. **`latest` を使った場合**、元の `docker pull`、`docker-compose.yml`、またはデプロイスクリプトを確認し、[GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases) と比較してください。
3. **フロントエンドが更新されたことだけを確認したい場合**、WebUI → 設定を開いて `Build ID` / `Build Time` を確認してください。これは静的アセットの新しさを確認するもので、Docker のリリースバージョンではありません。

**推奨**: 繰り返しの更新を避けるため、`latest` に頼るのではなく、`v3.12.0` のような固定バージョンタグを使用することをおすすめします。

---

## その他の問題

### Q15: 銘柄分析なしで大引け振り返りのみを実行する方法は？

**方法**:
```bash
# ローカル実行
python main.py --market-only

# GitHub Actions
# 手動トリガー時にモードを選択: market-only
```

---

### Q16: 分析結果の買い／様子見／売りのカウントが正しくない？

**原因**: 旧バージョンでは統計に正規表現マッチングを使用していたため、実際の推奨と一致しないことがありました。

**解決策**: 最新バージョンで修正済み。AI モデルが正確な統計のために `decision_type` フィールドを直接出力するようになりました。

---

## まだ質問がありますか？

上記の内容で問題が解決しない場合は、お気軽に：
1. [完全な設定ガイド](full-guide_EN.md) を確認する
2. [GitHub Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues) を検索または提出する
3. 最新の修正については [変更履歴](CHANGELOG.md) を確認する

---

*最終更新: 2026-04-20*
