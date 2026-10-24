import argparse
import concurrent.futures
import json
import math
import time
import urllib.parse
import urllib.request

import db

CN_REPO = "luoxuhai/chinese-novel"
CN_SOURCE = "luoxuhai/chinese-novel"
GUTENDEX_API = "https://gutendex.com/books"
GUTENDEX_SOURCE = "Gutendex / Project Gutenberg"
GUTENDEX_PAGE_SIZE = 32

HEADERS = {"User-Agent": "xiaoshuo-mvp/0.1"}


def http_json(url, retries=4, timeout=60):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(2 + i)
    raise RuntimeError(f"GET {url} failed: {last}")


def load_info_json(branch, path):
    quoted = urllib.parse.quote(path, safe="/")
    urls = (
        f"https://fastly.jsdelivr.net/gh/{CN_REPO}@{branch}/{quoted}",
        f"https://gcore.jsdelivr.net/gh/{CN_REPO}@{branch}/{quoted}",
        f"https://cdn.jsdelivr.net/gh/{CN_REPO}@{branch}/{quoted}",
        f"https://raw.githubusercontent.com/{CN_REPO}/{branch}/{quoted}",
    )
    for url in urls:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=25) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                time.sleep(1 + attempt)
    raise RuntimeError(f"cannot fetch {path}")


def ingest_chinese_novel():
    tree = None
    branch = None
    for b in ("master", "main"):
        try:
            data = http_json(f"https://api.github.com/repos/{CN_REPO}/git/trees/{b}?recursive=1", retries=3, timeout=90)
            if "tree" in data:
                tree, branch = data["tree"], b
                break
        except Exception:
            continue
    if tree is None:
        raise RuntimeError(f"unable to fetch repo tree of {CN_REPO}")
    info_paths = [t["path"] for t in tree if t.get("type") == "blob" and t["path"].endswith("info.json")]

    def fetch(path):
        try:
            return load_info_json(branch, path), path
        except Exception:
            return None, path

    rows = []
    failed = []
    done = 0
    total = len(info_paths)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(fetch, p) for p in info_paths]
        for fut in concurrent.futures.as_completed(futures):
            done += 1
            if done % 100 == 0:
                print(f"[chinese-novel] fetched {done}/{total}")
            meta, path = fut.result()
            if meta is None:
                failed.append(path)
                continue
            title = str(meta.get("name") or meta.get("title") or "").strip()
            if not title:
                continue
            author_obj = meta.get("author") or {}
            if isinstance(author_obj, dict):
                author = str(author_obj.get("name") or "").strip()
            else:
                author = str(author_obj).strip()
            book_dir = path.rsplit("/", 1)[0]
            url = f"https://github.com/{CN_REPO}/tree/{branch}/{urllib.parse.quote(book_dir, safe='/')}"
            rows.append((title, author, CN_SOURCE, url))
    for row in rows:
        db.upsert_book(*row)
    if failed:
        print(f"[chinese-novel] failed to fetch {len(failed)} info.json:")
        for p in failed:
            print("  ", p)
    print(f"[chinese-novel] {len(rows)}/{len(info_paths)} books ingested")
    return len(rows)


def parse_gutendex_page(data):
    rows = []
    for book in data.get("results", []):
        title = str(book.get("title") or "").strip()
        book_id = book.get("id")
        if not title or not book_id:
            continue
        names = [a.get("name", "").strip() for a in book.get("authors", []) if a.get("name")]
        rows.append((title, "; ".join(names), GUTENDEX_SOURCE, f"https://www.gutenberg.org/ebooks/{book_id}"))
    return rows


def ingest_gutendex(max_pages=None):
    first = http_json(f"{GUTENDEX_API}?copyright=false")
    count = int(first.get("count") or 0)
    total_pages = max(1, math.ceil(count / GUTENDEX_PAGE_SIZE))
    if max_pages:
        total_pages = min(total_pages, max_pages)
    pages = [first]
    rest = list(range(2, total_pages + 1))
    if rest:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            pages.extend(pool.map(lambda n: http_json(f"{GUTENDEX_API}?copyright=false&page={n}"), rest))
    rows = []
    for data in pages:
        rows.extend(parse_gutendex_page(data))
    for row in rows:
        db.upsert_book(*row)
    print(f"[gutendex] {len(rows)} books ingested ({total_pages} pages, count={count})")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="公版书元数据采集")
    parser.add_argument("--max-pages", type=int, default=None, help="Gutendex 最大采集页数（每页 32 条），缺省为全量")
    parser.add_argument("--skip-gutendex", action="store_true", help="跳过 Gutendex 采集")
    args = parser.parse_args()

    db.init_db()
    ingest_chinese_novel()
    gutendex_ok = True
    if args.skip_gutendex:
        print("[gutendex] skipped by --skip-gutendex")
    else:
        try:
            ingest_gutendex(args.max_pages)
        except Exception as e:
            gutendex_ok = False
            print(f"[gutendex] FAILED: {e}")
    for src, n in db.stats().items():
        print(f"  {src}: {n}")
    if not gutendex_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
