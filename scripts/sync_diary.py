#!/usr/bin/env python3
"""Obsidian Diary/blog の記事を Hugo 形式に変換して content/posts/ へ同期する。"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import frontmatter
except ImportError:
    print(
        "Error: python-frontmatter がインストールされていません。\n"
        "  pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

# --- 設定 ---
BLOG_DIR = Path(r"C:\Users\ymmt_\Documents\Life_and_Div\20_Personal\Diary\blog")
OUTPUT_DIR = "content/posts"
IMAGE_OUTPUT_DIR = "static/images"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNC_STATE_FILE = Path(__file__).resolve().parent / ".synced_files.json"

JST = timezone(timedelta(hours=9))

WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
IMAGE_EMBED_RE = re.compile(r"!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def load_sync_state() -> list[str]:
    if not SYNC_STATE_FILE.exists():
        return []
    try:
        data = json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: 同期記録の読み込みに失敗しました ({exc})。空の状態で続行します。")
    return []


def save_sync_state(filenames: list[str]) -> None:
    SYNC_STATE_FILE.write_text(
        json.dumps(sorted(filenames), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def mtime_to_date(path: Path) -> datetime:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=JST)


def title_from_filename(path: Path) -> str:
    stem = path.stem
    # YYYY-MM-DD- プレフィックスを除去
    if len(stem) > 11 and stem[4] == "-" and stem[7] == "-" and stem[10] == "-":
        stem = stem[11:]
    return stem.replace("-", " ").replace("_", " ")


def find_image(source_md: Path, image_name: str) -> Path | None:
    """記事周辺から画像ファイルを探す。"""
    candidates = [
        source_md.parent / image_name,
        source_md.parent / "attachments" / image_name,
    ]
    blog_root = BLOG_DIR.resolve()
    for parent in [source_md.parent, *source_md.parents]:
        if not parent.is_relative_to(blog_root):
            break
        candidates.append(parent / image_name)
        candidates.append(parent / "attachments" / image_name)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file() and resolved.is_relative_to(blog_root):
            return resolved
    return None


def convert_wikilinks(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        alias = match.group(2)
        page = match.group(1).strip()
        return alias if alias else page

    return WIKILINK_RE.sub(repl, text)


def convert_images(text: str, source_md: Path, image_dir: Path) -> str:
    image_dir.mkdir(parents=True, exist_ok=True)

    def repl(match: re.Match[str]) -> str:
        image_name = match.group(1).strip()
        alt = (match.group(2) or Path(image_name).stem).strip()
        src = find_image(source_md, image_name)
        if src is None:
            print(f"Warning: 画像が見つかりません [{source_md.name}]: {image_name}")
            return alt
        dest = image_dir / src.name
        if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(src, dest)
        return f"![{alt}](/images/{src.name})"

    return IMAGE_EMBED_RE.sub(repl, text)


def normalize_frontmatter(post: frontmatter.Post, source_md: Path) -> frontmatter.Post:
    if "title" not in post.metadata or not post.metadata["title"]:
        post.metadata["title"] = title_from_filename(source_md)

    if "date" not in post.metadata or not post.metadata["date"]:
        post.metadata["date"] = mtime_to_date(source_md)
    elif isinstance(post.metadata["date"], str):
        # frontmatter が文字列のまま返す場合はそのまま（YAML パース済みなら datetime）
        pass

    # publish フラグはフォルダで判定するため不要
    post.metadata.pop("publish", None)

    return post


def convert_file(source_md: Path, output_dir: Path, image_dir: Path) -> bool:
    try:
        raw = source_md.read_text(encoding="utf-8")
        post = frontmatter.loads(raw)
    except Exception as exc:
        print(f"Warning: フロントマターの解析に失敗しました [{source_md}]: {exc}")
        return False

    post = normalize_frontmatter(post, source_md)
    body = convert_wikilinks(post.content)
    body = convert_images(body, source_md, image_dir)
    post.content = body

    output_path = output_dir / source_md.name
    output_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return True


def collect_source_files() -> list[Path]:
    blog_root = BLOG_DIR.resolve()
    return sorted(
        p
        for p in blog_root.rglob("*.md")
        if p.is_file() and p.is_relative_to(blog_root)
    )


def main() -> int:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    blog_dir = BLOG_DIR
    if not blog_dir.is_dir():
        print(
            f"Error: BLOG_DIR が存在しません: {blog_dir}\n"
            "  パスを確認するか、Obsidian の Diary/blog フォルダを作成してください。",
            file=sys.stderr,
        )
        return 1

    output_dir = PROJECT_ROOT / OUTPUT_DIR
    image_dir = PROJECT_ROOT / IMAGE_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    sources = collect_source_files()
    previous_synced = set(load_sync_state())
    current_outputs: list[str] = []
    converted = 0
    skipped = 0

    for source_md in sources:
        if convert_file(source_md, output_dir, image_dir):
            current_outputs.append(source_md.name)
            converted += 1
        else:
            skipped += 1

    deleted = 0
    for filename in previous_synced - set(current_outputs):
        target = output_dir / filename
        if target.exists():
            target.unlink()
            deleted += 1
            print(f"Deleted: {filename}")

    save_sync_state(current_outputs)

    print()
    print("--- 同期レポート ---")
    print(f"  変換: {converted} 件")
    print(f"  スキップ: {skipped} 件")
    print(f"  削除: {deleted} 件")
    print(f"  出力先: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
