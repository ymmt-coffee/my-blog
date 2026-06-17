# Obsidian → Hugo ブログ自動公開システム 仕様書

## 1. 目的

Obsidian の `Diary/blog` フォルダに置いた記事を Hugo ブログに変換し、GitHub Pages 上で毎日決まった時刻にまとめて公開する。

私的な日記・メモ（`Diary/private`）とブログ記事（`Diary/blog`）を**フォルダで物理的に分離**し、公開対象を取り違えるリスクをなくすことを最優先とする。

---

## 2. 全体構成

### フォルダ配置

```
（Obsidian vault ルート）
├── 20_Personal/
│   └── Diary/
│       ├── private/                 ← 私的なメモ・日記（公開されない。Git にも上げない）
│       │   └── 2026-06-18-memo.md
│       └── blog/                    ← ここに入れた記事だけが公開対象
│           ├── 2026-06-17-zelda.md
│           └── 2026-06-20-cardgame.md
└── 30_Projects/
    └── 10_Apps/
        └── my-blog/                 ← Hugoプロジェクト（このフォルダだけGitHub管理）
            ├── .git/
            ├── hugo.toml
            ├── content/
            │   └── posts/           ← 変換後の記事が入る（スクリプトが生成）
            ├── scripts/
            │   └── sync_diary.py     ← 変換スクリプト（新規作成）
            ├── static/images/        ← 変換時にコピーされる画像
            ├── themes/PaperMod/
            └── .github/workflows/
                └── hugo.yml          ← 既存（cron設定を含む）
```

### 処理の流れ

1. ユーザーが記事を書く。公開したいものは `20_Personal/Diary/blog/` に、私的なメモは `20_Personal/Diary/private/` に置く
2. ローカルで変換スクリプト `sync_diary.py` を実行
   - `Diary/blog/` 内だけを走査し、各記事を Hugo 形式に変換して `my-blog/content/posts/` にコピー
   - `Diary/private/` には一切アクセスしない
3. ユーザーが `my-blog` を git push
4. GitHub Actions が **毎日定時（cron）** に Hugo をビルド
   - `date`（=公開日時）が現在時刻より前の記事だけが公開される
5. GitHub Pages に自動デプロイ

> ポイント: push は手動。公開タイミングの制御は GitHub Actions 側の cron + Hugo の未来日付除外に任せる。PC の常時起動は不要。

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
| `title` | 任意 | 記事タイトル。省略時はファイル名から生成 |
| `date` | 任意 | 公開日時。**この時刻を過ぎるとビルド時に公開される**。省略時はファイルの更新日時 |
| `tags` | 任意 | タグ |

`publish` フラグは不要（フォルダで判定するため）。

予約投稿したい場合は `date` を未来の日時にしておく。cron ビルドのタイミングでその時刻を過ぎていれば公開される。

---

## 4. 変換スクリプト `sync_diary.py` の仕様

### 配置と実行

- 配置: `my-blog/scripts/sync_diary.py`
- 実行: `python scripts/sync_diary.py`（`my-blog` ディレクトリ内で実行する想定）
- 言語: Python 3（標準ライブラリ中心。フロントマター解析に `python-frontmatter` か `PyYAML` を使用）

### 設定（スクリプト冒頭の定数）

```python
BLOG_DIR = "../../../20_Personal/Diary/blog"   # my-blog からの相対パス（要調整）
OUTPUT_DIR = "content/posts"
IMAGE_OUTPUT_DIR = "static/images"
```

> 注: `BLOG_DIR` の相対パスは実際のフォルダ階層に合わせて調整すること。`my-blog` が `30_Projects/10_Apps/` 配下、`blog` が `20_Personal/Diary/` 配下にあるので、vault ルートまで遡るパスになる。絶対パス指定でも可。`private/` フォルダは走査対象に含めないこと（`BLOG_DIR` より上を見に行かない）。

### 処理内容

1. `BLOG_DIR` 以下の `.md` ファイルを再帰的に走査する（`private/` には触れない）
2. 各ファイルのフロントマターを解析する
3. 以下の変換を行う:
   - **フロントマター変換**: `date` がなければファイルの mtime を補完。その他のフィールドはそのまま引き継ぐ
   - **wikilink 変換**: `[[ページ名]]` 形式のリンクを Hugo で扱える形に変換する。ブログ内で完結しない内部リンクは、プレーンテキスト化するか、リンク先も `blog/` にあるなら相対リンクにする（初期実装ではプレーンテキスト化でよい）
   - **画像変換**: `![[画像.png]]` 形式の Obsidian 埋め込み画像を、標準 Markdown 形式 `![](/images/画像.png)` に変換し、画像ファイルを `my-blog/static/images/` にコピーする
4. 変換結果を `OUTPUT_DIR`（`content/posts/`）にファイル名そのままで書き出す
5. **同期削除**: `blog/` からファイルを削除した、または `private/` へ移動した記事は、`content/posts/` 側からも削除する。スクリプトが出力したファイルのみを管理対象とする（出力済みファイル名を `scripts/.synced_files.json` などに記録し、前回出力分と今回対象を比較。手書きで置いた記事を誤って消さないようにする）

### 出力

- 標準出力に、変換した記事数・削除数を表示する（処理結果のレポート）

### エラーハンドリング

- フロントマターが壊れている記事は警告を出してスキップ（処理全体は止めない）
- `BLOG_DIR` が存在しない場合は明確なエラーメッセージを出して終了

---

## 5. Hugo 側の設定確認

### `hugo.toml` への追記・確認事項

- 未来日付の記事をビルド時に除外する設定が有効であること（Hugo はデフォルトで `buildFuture = false`。明示的に確認）
- `date` を公開日として扱う設定。PaperMod は `date` を公開日として扱うので追加設定は基本不要だが、念のため明示:

```toml
[frontmatter]
  date = ["date", "publishDate"]
```

### `.github/workflows/hugo.yml` の確認

- 既存のワークフローに cron が設定済み（`schedule: cron: '0 23 * * *'` = 日本時間 毎朝8時）
- `hugo --minify` でビルドしていること
- cron ビルドのたびに「その時点で `date` を過ぎた記事」が公開される

> 補足: Hugo は未来日付の記事をデフォルトでビルドしないため、cron で定期的にビルドを回すだけで「予約投稿」が成立する。記事を push した時点で未来日付なら公開されず、cron が回ったタイミングで時刻が来ていれば公開される。

---

## 6. Obsidian 側の設定

- `my-blog`（Hugoプロジェクト）が vault 内にあるため、Obsidian が `content/posts/` 内の Markdown をノートとして認識してしまう
- **対策**: Obsidian の「設定 → ファイルとリンク → 除外フォルダ」に `30_Projects/10_Apps/my-blog` を追加し、サイドバーから除外する

---

## 7. .gitignore 確認

`my-blog/.gitignore` に以下が含まれること:

```
# Hugo build output
/public/
/resources/_gen/
.hugo_build.lock

# OS
.DS_Store
Thumbs.db

# スクリプトの同期記録（任意。共有不要ならignore）
scripts/.synced_files.json
```

---

## 8. 実装の優先順位（Cursorへの指示）

1. **最優先**: `sync_diary.py` の基本機能（`Diary/blog/` の記事を変換コピー）。これが動けば公開フロー全体が回る
2. wikilink・画像の変換処理
3. 同期削除（削除・`private/` への移動への追従）
4. エラーハンドリングとレポート出力の整備

段階的に実装してよい。まずは 1 が動く状態を作り、ローカルで `python scripts/sync_diary.py` → `content/posts/` に記事が出力されることを確認してから次へ進むこと。

---

## 9. 動作確認の手順（実装後）

1. `Diary/blog/` にテスト記事を1本、`Diary/private/` に別の記事を1本書く
2. `python scripts/sync_diary.py` を実行 → `content/posts/` に `blog/` の記事だけが出ること、`private/` の記事が出ないことを確認
3. `hugo server -D` でローカルプレビュー
4. `date` を未来日時にした記事を用意し、`hugo server`（`-D` なし）では表示されないことを確認（予約投稿の挙動確認）
5. git push → GitHub Actions のビルドを確認 → 公開サイトで表示を確認
