"""Async web scraping with Python: httpx + asyncio, many pages at once.

Downloads the listing pages of https://books.toscrape.com (a scraping sandbox)
concurrently, with a concurrency limit, retries with backoff, and an optional
rotating residential proxy. Compare the time with the sequential version.

    pip install -r requirements.txt
    python async_scraper.py --pages 20 --concurrency 5
    python async_scraper.py --pages 20 --sequential      # for comparison
"""
import argparse
import asyncio
import os
import random
import time

import httpx
from bs4 import BeautifulSoup

URL = "https://books.toscrape.com/catalogue/page-{}.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def proxy_url() -> str | None:
    """Rotating residential gateway: every new connection gets a new IP (set FUSION_USER, FUSION_PASS)."""
    user, password = os.environ.get("FUSION_USER"), os.environ.get("FUSION_PASS")
    if not (user and password):
        return None
    return f"http://{user}-country-{os.environ.get('FUSION_COUNTRY', 'us')}:{password}@resi.fusionproxy.net:12286"


async def fetch(client: httpx.AsyncClient, url: str, limit: asyncio.Semaphore, attempts: int = 3) -> str:
    async with limit:  # at most N requests in flight
        for attempt in range(1, attempts + 1):
            try:
                r = await client.get(url)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                return r.text
            except (httpx.TransportError, httpx.HTTPStatusError):
                if attempt == attempts:
                    raise
                await asyncio.sleep(2 ** attempt + random.random())  # backoff with jitter


def parse(html: str) -> list[str]:
    return [a["title"] for a in BeautifulSoup(html, "html.parser").select("article.product_pod h3 a")]


async def main(pages: int, concurrency: int, sequential: bool) -> None:
    limit = asyncio.Semaphore(1 if sequential else concurrency)
    timeout = httpx.Timeout(30)
    async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, proxy=proxy_url(), follow_redirects=True) as client:
        start = time.perf_counter()
        tasks = [fetch(client, URL.format(n), limit) for n in range(1, pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.perf_counter() - start

    titles, failed = [], 0
    for res in results:
        if isinstance(res, Exception):
            failed += 1
        else:
            titles += parse(res)
    mode = "sequential" if sequential else f"async, {concurrency} at a time"
    print(f"{pages} pages ({mode}): {len(titles)} books in {elapsed:.1f} s, {failed} failed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--sequential", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.pages, a.concurrency, a.sequential))
