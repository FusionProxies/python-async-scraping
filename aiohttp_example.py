"""The same idea with aiohttp: concurrent requests through an authenticated proxy.

aiohttp takes the proxy per request (or trust_env=True to read HTTPS_PROXY).

    pip install -r requirements.txt
    export FUSION_USER=... FUSION_PASS=...
    python aiohttp_example.py
"""
import asyncio
import os

import aiohttp

USER, PASS = os.environ["FUSION_USER"], os.environ["FUSION_PASS"]
PROXY = "http://resi.fusionproxy.net:12286"


async def exit_ip(session: aiohttp.ClientSession, country: str) -> str:
    auth = aiohttp.BasicAuth(f"{USER}-country-{country}", PASS)  # sent to the proxy, not the site
    async with session.get("https://ipinfo.io/json", proxy=PROXY, proxy_auth=auth) as r:
        data = await r.json()
        return f"{country}: {data['ip']} ({data.get('country')}, {data.get('city')})"


async def main() -> None:
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        results = await asyncio.gather(*(exit_ip(session, c) for c in ["us", "de", "gb", "jp", "br"]), return_exceptions=True)
    for r in results:
        print(r if not isinstance(r, Exception) else f"failed: {type(r).__name__}")


asyncio.run(main())
