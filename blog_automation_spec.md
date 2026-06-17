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
│       │   └── 2026-06-18-memo.md
│       └── blog/                    ← ここに入れた記事だけが公開対象
│           ├── 2026-06-17-zelda.md
│           └── 2026-06-20-cardgame.md
└── 30_Projects/
    └── 10_Apps/
        └── my-blog/                 ← Hugoプロジェクト（このフォルダだけ GitHub 管理）
            ├── .git/
            ├── hugo.toml
            ├── publish.ps1            ← 同期〜push を一括実行するスクリプト
            ├── requirements.txt       ← Python 依存（python-frontmatter）
            ├── content/
            │   └── posts/           ← 変換後の記事が入る（sync_diary.py が生成）
            ├── scripts/
            │   ├── sync_diary.py    ← 変換スクリプト
            │   └── .synced_files.json  ← 同期管理用（gitignore 対象）
            ├── static/images/        ← 変換時にコピーされる画像
            ├── themes/PaperMod/
            └── .github/workflows/
                └── hugo.yml          ← push / cron でビルド・デプロイ
```

### 処理の流れ

1. ユーザーが記事を書く。公開したいものは `20_Personal/Diary/blog/` に、私的なメモは `20_Personal/Diary/private/` に置く
2. `publish.ps1` を実行（または `python scripts/sync_diary.py` のみ実行）
   - `Diary/blog/` 内だけを走査し、各記事を Hugo 形式に変換して `my-blog/content/posts/` に書き出す
   - `Diary/private/` には一切アクセスしない
3. `publish.ps1` が続けて `git add` → `git commit` → `git push` を実行
4. GitHub Actions が **push 時** および **毎日定時（cron）** に Hugo をビルド
   - `date`（=公開日時）が現在時刻より前の記事だけが公開される
5. GitHub Pages に自動デプロイ

> ポイント: 記事の push は `publish.ps1`（または手動 git）で行う。公開タイミングの制御は GitHub Actions 側の cron + Hugo の未来日付除外に任せる。PC の常時起動は不要。

> 安全設計: 公開されるかどうかは「どのフォルダに置いたか」だけで決まる。`blog/` に入れれば公開、`private/` に入れれば非公開。フラグの書き忘れ・書き間違いによる誤公開が原理的に起きない。公開・非公開の切り替えは Obsidian 上でファイルを `blog/` ⇔ `private/` へドラッグするだけ。

---

## 3. 記事の書き方（ユーザー側のルール）

`Diary/blog/` に置く記事のフロントマター例:

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
| `title` | 任意 | 記事タイトル。省略時はファイル名から生成（`YYYY-MM-DD-` プレフィックスは除去） |
| `date` | 任意 | 公開日時（JST 想定）。**この時刻を過ぎるとビルド時に公開される**。省略時はファイルの更新日時 |
| `tags` | 任意 | タグ |

`publish` フラグは不要（フォルダで判定するため）。

予約投稿したい場合は `date` を未来の日時にしておく。cron ビルドのタイミングでその時刻を過ぎていれば公開される。

---

## 4. 変換スクリプト `sync_diary.py` の仕様

### 配置と実行

- 配置: `my-blog/scripts/sync_diary.py`
- 実行: `python scripts/sync_diary.py`（`my-blog` ディレクトリ内で実行する想定。`publish.ps1` からも呼ばれる）
- 依存: Python 3 + `python-frontmatter`（`pip install -r requirements.txt`）

### 設定（スクリプト冒頭の定数）

```python
BLOG_DIR = Path(r"C:\Users\ymmt_\Documents\Life_and_Div\20_Personal\Diary\blog")  # 絶対パス
OUTPUT_DIR = "content/posts"          # PROJECT_ROOT からの相対パス
IMAGE_OUTPUT_DIR = "static/images"      # PROJECT_ROOT からの相対パス
```

> 注: `BLOG_DIR` は環境に合わせて絶対パスで指定する。`private/` フォルダは走査対象に含めない（`BLOG_DIR` より上を見に行かない）。

### 処理内容

1. `BLOG_DIR` 以下の `.md` ファイルを再帰的に走査する（`private/` には触れない）
2. 各ファイルのフロントマターを解析する
3. 以下の変換を行う:
   - **フロントマター変換**: `title` / `date` がなければ補完。`publish` フラグは除去。その他のフィールドはそのまま引き継ぐ
   - **wikilink 変換**: `[[ページ名]]` / `[[ページ名|表示名]]` / `[[ページ名#見出し]]` をプレーンテキスト化
   - **画像変換**: `![[画像.png]]` 形式を `![](/images/画像.png)` に変換し、画像ファイルを `static/images/` にコピーする。画像の探索順: 記事と同じフォルダ → `attachments/` サブフォルダ → 親ディレクトリ（`blog/` 内に限る）
4. 変換結果を `content/posts/` に**ファイル名そのまま**（フラット）で書き出す
5. **同期削除**: `blog/` から消えた記事は `content/posts/` 側からも削除する。スクリプトが出力したファイルのみを管理（`scripts/.synced_files.json` に記録。手書きで置いた記事は誤って消さない）

### 出力

- 標準出力に、変換・スキップ・削除件数と出力先を表示する（同期レポート）

### エラーハンドリング

- フロントマターが壊れている記事は警告を出してスキップ（処理全体は止めない）
- `BLOG_DIR` が存在しない場合は明確なエラーメッセージを出して終了
- Windows では標準出力を UTF-8 に設定して文字化けを抑制

---

## 5. 公開スクリプト `publish.ps1` の仕様

### 配置と実行

- 配置: `my-blog/publish.ps1`
- 実行例:
  - ターミナル: `.\publish.ps1`（`my-blog` 内、またはフルパス指定）
  - Obsidian Shell Commands プラグイン（後述）

### 処理内容（順番に実行）

1. `python scripts/sync_diary.py`
2. `git add .`
3. `git commit -m "update posts"`（ステージ済み変更がなければスキップ。エラーで止まらない）
4. `git push`

各ステップの成否を `[OK]` / `[FAILED]` でコンソールに表示する。

### 実装上の注意

- 先頭で `$PSScriptRoot` に `Set-Location` し、どこから実行されても `my-blog` 直下で動作する
- Obsidian 等からの実行で文字化けしないよう、UTF-8 出力設定を先頭で行う

---

## 6. Hugo 側の設定

### `hugo.toml`

```toml
baseURL = "https://ymmt-coffee.github.io/my-blog/"
buildFuture = false

[frontmatter]
  date = ["date", "publishDate"]
```

- `baseURL` は実際の GitHub Pages URL に合わせる（プレースホルダーのままだと記事リンクが 404 になる）
- `buildFuture = false` で未来日付の記事をビルド時に除外

### ローカルプレビュー

| 目的 | コマンド |
|---|---|
| 下書きも含めて表示 | `hugo server -D --baseURL http://localhost:1313/` |
| 未来日付の予約投稿も確認 | 上記に `-F` を追加 |

> `-D` は下書き（`draft: true`）用。未来日付の表示には `-F` が必要。ローカルでは `--baseURL http://localhost:1313/` を付けないと、記事リンクが本番 URL を指してしまう。

### `.github/workflows/hugo.yml`

- `push`（main ブランチ）と cron（`0 23 * * *` = 日本時間 毎朝8時）でビルド
- `hugo --minify` でビルド
- cron ビルドのたびに「その時点で `date` を過ぎた記事」が公開される

---

## 7. Obsidian 側の設定

### 除外フォルダ

- `my-blog` が vault 内にあるため、Obsidian が `content/posts/` 内の Markdown をノートとして認識してしまう
- **対策**: 「設定 → ファイルとリンク → 除外フォルダ」に `30_Projects/10_Apps/my-blog` を追加

### Shell Commands プラグイン（任意）

Obsidian から `publish.ps1` を実行する場合のコマンド例（**1行で記述すること。改行を入れると `-File` にパスが渡らず失敗する**）:

```
powershell -ExecutionPolicy Bypass -File "C:\Users\ymmt_\Documents\Life_and_Div\30_Projects\10_Apps\my-blog\publish.ps1"
```

---

## 8. .gitignore

`my-blog/.gitignore` に以下が含まれること:

```
# Hugo build output
/public/
/resources/_gen/
.hugo_build.lock

# OS
.DS_Store
Thumbs.db

# スクリプトの同期記録
scripts/.synced_files.json
```

---

## 9. 動作確認の手順

1. 初回のみ: `pip install -r requirements.txt`
2. `Diary/blog/` にテスト記事を1本、`Diary/private/` に別の記事を1本書く
3. `python scripts/sync_diary.py`（または `.\publish.ps1`）を実行
   - `content/posts/` に `blog/` の記事だけが出ること
   - `private/` の記事が出ないこと
4. `hugo server -D --baseURL http://localhost:1313/` でローカルプレビュー
5. `date` を未来日時にした記事は `-F` なしでは表示されないことを確認（予約投稿の挙動）
6. `publish.ps1` または手動 `git push` → GitHub Actions のビルドを確認 → https://ymmt-coffee.github.io/my-blog/ で表示を確認

---

## 10. 実装済み機能一覧

- [x] `sync_diary.py` — `Diary/blog/` の記事を Hugo 形式に変換コピー
- [x] wikilink・画像の変換処理
- [x] 同期削除（`blog/` からの削除・`private/` への移動への追従）
- [x] エラーハンドリングとレポート出力
- [x] `publish.ps1` — 同期〜git push の一括実行
- [x] `hugo.toml` — `baseURL` / `buildFuture` / `[frontmatter]` 設定
- [x] Obsidian Shell Commands からの実行対応
