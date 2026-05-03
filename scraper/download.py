import re
import argparse
import json
from pathlib import Path
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://www.futures.co.kr"
BBS_ID = "BBSMSTR_000000000251"
SEARCH_URL = f"{BASE_URL}/bbs/boardSearch.do"
CONTENT_URL = f"{BASE_URL}/content/Getcontent.do?content=3000031"
DAILY_PATTERN = re.compile(r"NHF\+Daily\+Metal\+Bulletin\+(\d{8})\.pdf")


def extract_pdf_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a_tag in soup.select("td.fileDown a"):
        href = a_tag.get("href", "")
        match = DAILY_PATTERN.search(href)
        if not match:
            continue
        date_str = match.group(1)
        date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        file_id_match = re.search(r"atchFileId=(FILE_\d+)", href)
        if not file_id_match:
            continue
        links.append({
            "date": date,
            "file_id": file_id_match.group(1),
            "url": href,
        })
    return links


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    })
    session.get(BASE_URL)
    session.get(CONTENT_URL)
    return session


def fetch_page(session: requests.Session, page: int) -> str:
    if page == 1:
        resp = session.get(CONTENT_URL)
    else:
        resp = session.post(SEARCH_URL, data={
            "bbsId": BBS_ID,
            "pageIndex": str(page),
            "url": "content/research/KR_interestRate",
        })
    return resp.text


def download_pdf(session: requests.Session, url: str, dest: Path) -> bool:
    full_url = f"{BASE_URL}{url}" if url.startswith("/") else url
    resp = session.get(full_url)
    if resp.status_code == 200 and len(resp.content) > 0:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return True
    return False


def existing_dates(data_dir: Path) -> set[str]:
    return {f.stem for f in (data_dir / "daily").glob("*.json")}


def run(mode: str, data_dir: Path, tmp_dir: Path, max_pages: int = 7):
    session = create_session()
    done = existing_dates(data_dir)
    downloaded = []

    pages = range(1, 2) if mode == "latest" else range(1, max_pages + 1)
    for page_num in pages:
        html = fetch_page(session, page_num)
        links = extract_pdf_links(html)
        if not links:
            continue

        for link in links:
            if link["date"] in done:
                continue
            dest = tmp_dir / f"{link['date']}.pdf"
            if download_pdf(session, link["url"], dest):
                downloaded.append({"date": link["date"], "path": str(dest)})
                print(f"Downloaded: {link['date']}")

        if mode == "latest" and downloaded:
            break

    manifest = tmp_dir / "manifest.json"
    manifest.write_text(json.dumps(downloaded, ensure_ascii=False, indent=2))
    print(f"Total downloaded: {len(downloaded)}")
    return downloaded


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["latest", "backfill"], default="latest")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--tmp-dir", type=Path, default=Path("tmp/pdfs"))
    ap.add_argument("--max-pages", type=int, default=7)
    args = ap.parse_args()
    run(args.mode, args.data_dir, args.tmp_dir, args.max_pages)
