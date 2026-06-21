# Obsidian → Hugo ブログ自動公開システム 仕様書

## 1. 目的

Obsidian の `Diary/blog` フォルダに置いた記事を Hugo ブログに変換し、GitHub Pages 上で毎日決まった時刻にまとめて公開する。

私的な日記・メモ（`Diary/private`）とブログ記事（`Diary/blog`）を**フォルダで物理的に分離**し、公開対象を取り違えるリスクをなくすことを最優先とする。

---

## 2. 全体構成

### フォルダ配置

```
（Obsidian vault ルート = Life_and_Div）
├── 20_Personal/
│   └── Diary/
│       ├── private/                 ← 私的なメモ・日記（公開されない。Git にも上げない）
│       └── blog/                    ← ここに入れた記事だけが公開対象
└── 30_Projects/
    └── 10_Apps/
        └── my-blog/                 ← Hugoプロジェクト（このフォルダだけ GitHub 管理）
            ├── .git/
            ├── hugo.toml
            ├── publish.ps1            ← 同期〜push を一括実行
            ├── requirements.txt
            ├── blog_automation_spec.md
            ├── assets/css/extended/
            │   └── custom.css         ← サイトデザインのカスタム CSS
            ├── layouts/
            │   ├── list.html          ← トップページの一覧レイアウト
            │   └── _partials/         ← テーマ上書き用パーシャル
            ├── content/posts/         ← sync_diary.py が生成
            ├── scripts/
            │   ├── sync_diary.py
            │   └── .synced_files.json  ← gitignore 対象
            ├── static/images/
            ├── themes/PaperMod/
            └── .github/workflows/hugo.yml
```

### 処理の流れ

1. ユーザーが記事を書く。公開対象は `Diary/blog/`、非公開は `Diary/private/`
2. `publish.ps1` を実行（または `python scripts/sync_diary.py` のみ）
3. `git push`（`publish.ps1` が自動実行）
4. GitHub Actions が push 時および cron（毎朝8時 JST）で Hugo をビルド
5. GitHub Pages にデプロイ

> 安全設計: 公開可否はフォルダ配置だけで決まる。`publish` フラグは不要。

---

## 3. 記事の書き方（ユーザー側のルール）

```markdown
---
title: "ゼルダの新作をクリアした"
date: 2026-06-20T08:00:00+09:00
tags: ["ゲーム", "ゼルダ"]
---

本文をここに書く。
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `title` | 任意 | 省略時はファイル名から生成（`YYYY-MM-DD-` プレフィックス除去） |
| `date` | 任意 | 公開日時（JST）。省略時はファイルの更新日時 |
| `tags` | 任意 | タグ |

予約投稿は `date` を未来に設定。cron ビルド時に時刻を過ぎていれば公開される。

---

## 4. 変換スクリプト `sync_diary.py`

### 設定

```python
BLOG_DIR = Path(r"C:\Users\ymmt_\Documents\Life_and_Div\20_Personal\Diary\blog")
OUTPUT_DIR = "content/posts"
IMAGE_OUTPUT_DIR = "static/images"
```

### 処理

1. `BLOG_DIR` 以下の `.md` を再帰走査（`private/` には触れない）
2. フロントマター解析・変換（wikilink プレーンテキスト化、画像を `static/images/` へコピー）
3. `content/posts/` へファイル名そのままで出力
4. 同期削除（`scripts/.synced_files.json` で管理。手書き記事は消さない）

### 実行

```powershell
pip install -r requirements.txt   # 初回のみ
python scripts/sync_diary.py
```

---

## 5. 公開スクリプト `publish.ps1`

1. `python scripts/sync_diary.py`
2. `git add .`
3. `git commit -m "update posts"`（変更なしならスキップ）
4. `git push`

- `$PSScriptRoot` に移動してから実行（どこから起動しても動作）
- UTF-8 出力設定あり

Obsidian Shell Commands（**1行で記述**）:

```
powershell -ExecutionPolicy Bypass -File "C:\Users\ymmt_\Documents\Life_and_Div\30_Projects\10_Apps\my-blog\publish.ps1"
```

---

## 6. Hugo 設定（`hugo.toml`）

```toml
baseURL = "https://ymmt-coffee.github.io/my-blog/"
title = "logs"
theme = "PaperMod"
buildFuture = false

[frontmatter]
  date = ["date", "publishDate"]

[params]
  ShowReadingTime = false      # 読了時間は非表示
  disableSpecial1stPost = true # PaperMod 標準の先頭記事拡大を無効化
```

### ローカルプレビュー

```powershell
hugo server -D --baseURL http://localhost:1313/
```

| フラグ | 用途 |
|---|---|
| `-D` | 下書き（`draft: true`）を含める |
| `-F` | 未来日付の予約投稿を含める |

---

## 7. サイトデザイン・レイアウト

PaperMod をベースに、以下をカスタマイズしている。

### フォント・行間

- フォント: **Noto Sans JP**（Google Fonts、`layouts/_partials/extend_head.html`）
- 行間: `line-height: 1.9`（`assets/css/extended/custom.css`）

### ヘッダー

- サイトタイトル「logs」を中央寄せ
- ライト/ダーク切替ボタンはタイトル右隣（折り返さない）
- スマホ（768px 以下）: 上部余白を追加（`safe-area-inset-top` 対応）

### トップページ一覧

| 区分 | 表示 | 件数 |
|---|---|---|
| **最新記事（フィーチャー）** | 大きなタイトル、3行抜粋、日付 · 経過時間、「続きを読む →」 | 1件 |
| **旧記事（アーカイブ）** | カード形式。タイトル（左）+ 日付（右）、1行抜粋 | 最大9件/ページ |

- 1ページあたり合計10件（Hugo デフォルト paginate）。2ページ目以降はフィーチャーなし
- フィーチャー記事はクリックで記事ページへ（全文は個別ページで閲覧）
- 挨拶文（homeInfoParams）は使用しない

### 日付・経過時間の表示

| 場所 | 最新記事 | 旧記事 |
|---|---|---|
| トップ（フィーチャー） | 日付 · 経過時間 | — |
| トップ（アーカイブカード） | — | 日付のみ |
| 記事ページ | 日付 · 経過時間 | 日付のみ |

- **読了時間は表示しない**
- **経過時間**（`2日前` など）は最新記事のみ（`layouts/_partials/relative_time_ja.html`）
- 最新記事の判定: `layouts/_partials/is_latest_post.html`

### カスタムファイル一覧

| ファイル | 役割 |
|---|---|
| `layouts/list.html` | トップページのフィーチャー/アーカイブ切替 |
| `layouts/_partials/home_featured.html` | 最新記事ブロック |
| `layouts/_partials/home_archive_entry.html` | 旧記事カード |
| `layouts/_partials/post_meta.html` | 記事ページのメタ情報 |
| `layouts/_partials/post_entry.html` | タグ一覧等の標準リスト項目 |
| `layouts/_partials/post_summary.html` | 抜粋テキスト |
| `layouts/_partials/date_and_elapsed.html` | 日付 · 経過時間 |
| `layouts/_partials/relative_time_ja.html` | 経過時間の日本語化 |
| `layouts/_partials/is_latest_post.html` | 最新記事判定 |
| `layouts/_partials/extend_head.html` | Google Fonts 読み込み |
| `assets/css/extended/custom.css` | デザイン CSS |

---

## 8. Obsidian 側の設定

- **除外フォルダ**: `30_Projects/10_Apps/my-blog`
- **Shell Commands**: 上記 `publish.ps1` を1行で登録

---

## 9. .gitignore

```
/public/
/resources/_gen/
.hugo_build.lock
.DS_Store
Thumbs.db
scripts/.synced_files.json
```

---

## 10. 動作確認の手順

1. `pip install -r requirements.txt`
2. `Diary/blog/` に記事を置き `python scripts/sync_diary.py` を実行
3. `hugo server -D --baseURL http://localhost:1313/` でプレビュー
4. トップ: フィーチャー1件 + 旧記事カード。旧記事は日付のみ
5. 最新記事ページ: 日付 · 経過時間。旧記事ページ: 日付のみ
6. `.\publish.ps1` → https://ymmt-coffee.github.io/my-blog/ で確認

---

## 11. 実装済み機能一覧

- [x] Obsidian → Hugo 同期（`sync_diary.py`）
- [x] wikilink・画像変換、同期削除
- [x] `publish.ps1`（Obsidian Shell Commands 対応）
- [x] GitHub Pages デプロイ（push + cron）
- [x] カスタムトップページ（フィーチャー + アーカイブ）
- [x] Noto Sans JP、行間 1.9
- [x] 最新記事のみ経過時間表示
- [x] スマホ向けヘッダー調整
