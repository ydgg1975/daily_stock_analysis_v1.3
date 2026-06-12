# コントリビューションガイド

コントリビューションへのご関心ありがとうございます！あらゆる種類の貢献を歓迎します。

## 🐛 バグ報告

1. まず [Issues](https://github.com/ZhuLinsen/daily_stock_analysis/issues) を検索し、すでに報告されていないか確認してください。
2. **Bug Report** テンプレートを使って新しい Issue を作成してください。
3. 詳細な再現手順と環境情報を記載してください。

## 💡 機能提案

1. Issues を検索し、その提案がまだ挙げられていないことを確認してください。
2. **Feature Request** テンプレートを使って新しい Issue を作成してください。
3. ユースケースと期待される挙動を詳細に記述してください。

## 🔧 コードの提出

### 開発環境のセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 依存関係をインストール
pip install -r requirements.txt

# 環境変数を設定
cp .env.example .env
# .env を編集し、必要な API キーを入力してください
```

### コントリビューションのワークフロー

1. 本リポジトリを Fork します。
2. フィーチャーブランチを作成します：`git checkout -b feature/your-feature`
3. 変更をコミットします：`git commit -m 'feat: add some feature'`
4. ブランチをプッシュします：`git push origin feature/your-feature`
5. `main` に対して Pull Request を作成します。

### コミットメッセージ規約

本プロジェクトは [Conventional Commits](https://www.conventionalcommits.org/) に従います：

```
feat:     新機能
fix:      バグ修正
docs:     ドキュメント更新
style:    コードフォーマット（ロジック変更なし）
refactor: コードのリファクタリング
perf:     パフォーマンス改善
test:     テスト関連の変更
chore:    ビルド／ツール関連の変更
```

例：

```
feat: add DingTalk bot support
fix: handle 429 rate-limit with retry backoff
docs: update README deployment section
```

### コードスタイル

- Python コードは PEP 8 に従います（行の長さ：120）。
- 関数とクラスには docstring を追加してください。
- 自明でないロジックにはコメントを追加してください。
- 新機能を追加する際は、関連するドキュメントを更新してください。

### CI チェック

PR を作成すると、CI が自動的に以下の PR チェックを実行します：

| チェック | 説明 | 必須 |
|-------|-------------|:--------:|
| `backend-gate` | `scripts/ci_gate.sh` — py_compile + flake8 の重大エラー + `./scripts/test.sh code` + `./scripts/test.sh yfinance` + オフライン pytest | ✅ |
| `docker-build` | Docker イメージのビルドと主要モジュールのインポート smoke テスト | ✅ |
| `web-gate` | `npm run lint` + `npm run build`（`apps/dsa-web/` に変更があった場合にトリガー） | ✅（トリガー時） |

別途、リポジトリには `.github/workflows/network-smoke.yml` にブロッキングではない `network-smoke` ワークフローもありますが、これは `schedule` と `workflow_dispatch` によってのみトリガーされ、プルリクエストではトリガーされません。

**ローカルでチェックを実行する：**

```bash
# バックエンドゲート（推奨）
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh

# フロントエンドゲート（apps/dsa-web/ を変更した場合のみ）
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

### ドキュメント同期ルール

中国語のコアドキュメント（例：`docs/full-guide.md`）を変更する場合、PR の説明には対応する英語ドキュメントを更新したかどうかを**必ず記載**してください。更新していない場合は、その理由を説明してください。

## 📋 優先的に貢献を募集している領域

- 🔔 新しい通知チャネル（例：Slack、Matrix）
- 🤖 新しい AI モデルの統合
- 📊 新しいデータソースアダプター
- 🐛 バグ修正とパフォーマンス改善
- 📖 ドキュメントの改善と翻訳

## ❓ 質問

お気軽にどうぞ：
- Issue を作成して議論する。
- 既存の Issue や Discussions を閲覧する。

コントリビューションありがとうございます！🎉
