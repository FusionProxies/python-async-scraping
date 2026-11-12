<p align="center">
  <a href="https://fusionproxy.net/?utm_source=github&utm_medium=python-async-scraping">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/FusionProxies/.github/main/assets/logo-on-dark.png">
      <img src="https://raw.githubusercontent.com/FusionProxies/.github/main/assets/logo-on-light.png" alt="Fusion Proxy" height="52">
    </picture>
  </a>
</p>

# Async web scraping in Python with asyncio, httpx and aiohttp

Scraping one page at a time spends most of its time waiting for the network. With `asyncio` you send many requests at once and wait for all of them together. This guide shows the pattern that works in practice: a shared async client, a **concurrency limit**, **retries with backoff**, and **proxies**, with httpx and with aiohttp.

```bash
pip install -r requirements.txt
python async_scraper.py --pages 20 --sequential
python async_scraper.py --pages 20 --concurrency 5
python async_scraper.py --pages 20 --concurrency 10
```

Measured on [books.toscrape.com](https://books.toscrape.com), a scraping sandbox:

```
20 pages (sequential): 400 books in 3.3 s, 0 failed
20 pages (async, 5 at a time): 400 books in 1.1 s, 0 failed
20 pages (async, 10 at a time): 400 books in 0.8 s, 0 failed
```

## The pattern

```python
import asyncio
import httpx

async def fetch(client, url, limit):
    async with limit:                      # at most N requests in flight
        r = await client.get(url)
        r.raise_for_status()
        return r.text

async def main(urls):
    limit = asyncio.Semaphore(5)
    async with httpx.AsyncClient(timeout=30) as client:   # one client, shared connections
        return await asyncio.gather(*(fetch(client, u, limit) for u in urls), return_exceptions=True)

pages = asyncio.run(main(urls))
```

1. **One client for all requests.** It reuses connections; creating a client per request throws that away.
2. **A semaphore.** Without it, `gather` fires every request at once: 10,000 URLs means 10,000 simultaneous connections, which gets you blocked and can crash your machine.
3. **`return_exceptions=True`.** One failed page should not throw away the 999 that worked.

## Retries with backoff

```python
for attempt in range(1, attempts + 1):
    try:
        r = await client.get(url)
        if r.status_code in (429, 500, 502, 503, 504):
            raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
        return r.text
    except (httpx.TransportError, httpx.HTTPStatusError):
        if attempt == attempts:
            raise
        await asyncio.sleep(2 ** attempt + random.random())
```

Use `asyncio.sleep`, never `time.sleep`, inside async code: `time.sleep` freezes every task.

## Proxies with httpx

```python
proxy = "http://USERNAME-country-us:PASSWORD@resi.fusionproxy.net:12286"
async with httpx.AsyncClient(proxy=proxy, timeout=30) as client:
    ...
```

With a rotating residential gateway, every new connection gets a new IP, so concurrent requests are spread over many IPs automatically. `async_scraper.py` uses the proxy when `FUSION_USER` and `FUSION_PASS` are set.

## Proxies with aiohttp

aiohttp takes the proxy per request, with the credentials in `proxy_auth`:

```python
auth = aiohttp.BasicAuth("USERNAME-country-de", "PASSWORD")
async with session.get("https://ipinfo.io/json", proxy="http://resi.fusionproxy.net:12286", proxy_auth=auth) as r:
    data = await r.json()
```

[`aiohttp_example.py`](aiohttp_example.py) asks for five countries at once:

```
us: 70.173.255.209 (US, Las Vegas)
gb: 81.111.48.195 (GB, Hartlepool)
jp: 123.230.4.216 (JP, Nagoya)
...
```

For SOCKS5 with aiohttp, use the `aiohttp-socks` package. `trust_env=True` on the session makes aiohttp read `HTTPS_PROXY`.

## How much concurrency?

- Start with 5 per website and raise it while the error rate stays at zero.
- `429` or a growing number of timeouts means you are too fast: lower it.
- Through a proxy, latency per request is higher, so the same concurrency gives a lower rate; that is fine, raise concurrency rather than removing delays.
- Respect the site: a scraper should never be what slows a website down.

## httpx or aiohttp?

| | httpx | aiohttp |
|---|---|---|
| API | Same as requests, sync and async | Async only |
| Proxy | `proxy=` on the client | `proxy=` per request or `trust_env` |
| HTTP/2 | Yes (`http2=True`) | No |
| Speed at very high concurrency | Good | Usually a bit faster |

Both work well; httpx is easier if you already know requests.

## Related

- [python-web-scraping](https://github.com/FusionProxies/python-web-scraping): the requests + BeautifulSoup basics
- [rotating-proxies-python](https://github.com/FusionProxies/rotating-proxies-python): rotate a proxy list and drop dead proxies
- [scrapy-proxy-middleware](https://github.com/FusionProxies/scrapy-proxy-middleware): Scrapy does async crawling for you

[Fusion Proxy residential proxies](https://fusionproxy.net/proxies/residential?utm_source=github&utm_medium=python-async-scraping) from $2.95/GB, with a [free trial](https://fusionproxy.net/free-trial?utm_source=github&utm_medium=python-async-scraping).

## License

MIT, see [LICENSE](LICENSE).
