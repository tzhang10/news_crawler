#!/usr/bin/env python3
import argparse, asyncio, csv, os, sys, time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Set, Tuple, Optional
from urllib.parse import urlparse, urljoin, urldefrag

import aiohttp
from bs4 import BeautifulSoup
import urllib.robotparser as robotparser

SEEDS = {
    "nytimes":  "https://www.nytimes.com/",
    "wsj":      "https://www.wsj.com/",
    "foxnews":  "https://www.foxnews.com/",
    "usatoday": "https://www.usatoday.com/",
    "latimes":  "https://www.latimes.com/",
}

# --------- Helpers
def normalize_url(base: str, href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith("mailto:") or href.startswith("javascript:"):
        return None
    # join relative, drop fragment
    try:
        u = urljoin(base, href)
        u, _ = urldefrag(u)
        parsed = urlparse(u)
        if not parsed.scheme.startswith("http"):
            return None
        return u
    except Exception:
        return None

def host_in_domain(host: Optional[str], domain: str) -> bool:
    if not host:
        return False
    return host == domain or host.endswith("." + domain)

def domain_from_seed(seed_url: str) -> str:
    return urlparse(seed_url).hostname

def content_main_type(content_type: Optional[str]) -> str:
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()

# --------- Stats
@dataclass
class SizeBuckets:
    lt1k: int = 0
    k1_10: int = 0
    k10_100: int = 0
    k100_1m: int = 0
    ge1m: int = 0

    def add(self, nbytes: int):
        if nbytes < 1024: self.lt1k += 1
        elif nbytes < 10*1024: self.k1_10 += 1
        elif nbytes < 100*1024: self.k10_100 += 1
        elif nbytes < 1024*1024: self.k100_1m += 1
        else: self.ge1m += 1

class Stats:
    def __init__(self, site: str):
        self.site = site
        self.attempted = 0
        self.succeeded = 0
        self.failed_or_aborted = 0
        self.by_status = Counter()
        self.by_content_type = Counter()
        self.sizes = SizeBuckets()

    def on_attempt(self, status: int):
        self.attempted += 1
        self.by_status[status] += 1
        if 200 <= status < 300:
            self.succeeded += 1
        else:
            self.failed_or_aborted += 1

    def on_visit(self, nbytes: int, content_type: str):
        self.sizes.add(nbytes)
        self.by_content_type[content_type] += 1

# --------- Politeness controller (global delay between requests)
class Politeness:
    def __init__(self, delay_ms: int):
        self._delay = delay_ms / 1000.0
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self._delay:
                await asyncio.sleep(self._delay - delta)
            self._last = time.monotonic()

# --------- Crawler
class Crawler:
    def __init__(self, seed_url: str, out_dir: Path, site_key: str,
                 max_pages: int, max_depth: int, concurrency: int, politeness_ms: int):
        self.seed_url = seed_url
        self.domain = domain_from_seed(seed_url)
        self.out_dir = out_dir
        self.site_key = site_key
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.politeness = Politeness(politeness_ms)

        self.seen: Set[str] = set()
        self.to_crawl: deque[Tuple[str,int]] = deque()
        self.to_crawl.append((seed_url, 0))

        self.session: Optional[aiohttp.ClientSession] = None
        self.sem = asyncio.Semaphore(concurrency)
        self.stats = Stats(site_key)

        # CSVs
        self.fetch_fp = open(out_dir / f"fetch_{site_key}.csv", "w", newline="", encoding="utf-8")
        self.fetch_csv = csv.writer(self.fetch_fp)
        self.fetch_csv.writerow(["URL","Status"])

        self.visit_fp = open(out_dir / f"visit_{site_key}.csv", "w", newline="", encoding="utf-8")
        self.visit_csv = csv.writer(self.visit_fp)
        self.visit_csv.writerow(["URL","Size","#Outlinks","Content-Type"])

        self.urls_fp = open(out_dir / f"urls_{site_key}.csv", "w", newline="", encoding="utf-8")
        self.urls_csv = csv.writer(self.urls_fp)
        self.urls_csv.writerow(["URL","Indicator"])

        # robots.txt
        self.rp = robotparser.RobotFileParser()
        robots_url = f"{urlparse(seed_url).scheme}://{self.domain}/robots.txt"
        self._robots_ok = True
        self._robots_url = robots_url

    async def _init_session(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        # load robots
        try:
            async with self.session.get(self._robots_url, headers={"User-Agent": "usc-crawler"}) as resp:
                text = await resp.text(errors="ignore")
                self.rp.parse(text.splitlines())
        except Exception:
            # If robots cannot be fetched, be permissive (common in assignments);
            # your instructor can adjust if needed.
            self._robots_ok = False

    async def close(self):
        for fp in (self.fetch_fp, self.visit_fp, self.urls_fp):
            try: fp.flush(); fp.close()
            except Exception: pass
        if self.session:
            await self.session.close()

    def record_url_indicator(self, url: str, ok: bool):
        self.urls_csv.writerow([url, "OK" if ok else "N_OK"])

    def allowed_by_robots(self, url: str) -> bool:
        if not self._robots_ok:
            return True
        try:
            return self.rp.can_fetch("usc-crawler", url)
        except Exception:
            return True

    async def fetch_one(self, url: str) -> Tuple[int, bytes, str]:
        assert self.session is not None
        await self.politeness.wait()
        headers = {"User-Agent": "usc-crawler"}
        try:
            async with self.session.get(url, headers=headers, allow_redirects=True) as resp:
                content = await resp.read()
                ctype = resp.headers.get("Content-Type","")
                status = resp.status
                return status, content, ctype
        except Exception:
            return 599, b"", ""

    async def worker(self):
        while self.to_crawl and len(self.seen) < self.max_pages:
            url, depth = self.to_crawl.popleft()
            if url in self.seen:
                continue
            self.seen.add(url)

            parsed = urlparse(url)
            in_dom = host_in_domain(parsed.hostname, self.domain)
            self.record_url_indicator(url, in_dom)
            if not in_dom:
                continue
            if depth > self.max_depth:
                continue
            if not self.allowed_by_robots(url):
                # treat as “skipped” without fetch attempt
                continue

            async with self.sem:
                status, content, ctype = await self.fetch_one(url)
                # record fetch attempt (every try, per spec)
                self.fetch_csv.writerow([url, status])
                self.stats.on_attempt(status)

                if 200 <= status < 300:
                    # visit
                    main_ctype = content_main_type(ctype)
                    outlinks = 0
                    if main_ctype in ("text/html", "application/xhtml+xml"):
                        soup = BeautifulSoup(content, "html.parser")
                        links = set()
                        for a in soup.find_all("a", href=True):
                            nu = normalize_url(url, a.get("href"))
                            if nu:
                                links.add(nu)
                        outlinks = len(links)
                        # enqueue only in-domain links; still log all in urls_*.csv via should-visit logic later
                        for link in links:
                            host = urlparse(link).hostname
                            self.record_url_indicator(link, host_in_domain(host, self.domain))
                            if host_in_domain(host, self.domain) and link not in self.seen:
                                if len(self.seen) + len(self.to_crawl) < self.max_pages:
                                    self.to_crawl.append((link, depth + 1))
                    # size + content-type stats + visit csv
                    self.stats.on_visit(len(content), main_ctype)
                    self.visit_csv.writerow([url, len(content), outlinks, main_ctype])

    async def run(self):
        await self._init_session()
        workers = [asyncio.create_task(self.worker()) for _ in range(self.concurrency)]
        await asyncio.gather(*workers)
        await self.close()
        self.write_report()

    def write_report(self):
        p = self.out_dir / f"CrawlReport_{self.site_key}.txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"Name: {os.getenv('USER','student')}\n")
            f.write("USC ID: XXXXXXXXX\n")
            f.write(f"News site crawled: {self.site_key}\n\n")

            f.write("Fetch Statistics\n=================\n")
            f.write(f"# fetches attempted: {self.stats.attempted}\n")
            f.write(f"# fetches succeeded: {self.stats.succeeded}\n")
            f.write(f"# fetches failed or aborted: {self.stats.failed_or_aborted}\n\n")

            f.write("Status Codes\n============\n")
            for code in sorted(self.stats.by_status):
                f.write(f"{code}: {self.stats.by_status[code]}\n")
            f.write("\n")

            f.write("File Sizes\n==========\n")
            f.write(f"< 1KB: {self.stats.sizes.lt1k}\n")
            f.write(f"1KB ~ <10KB: {self.stats.sizes.k1_10}\n")
            f.write(f"10KB ~ <100KB: {self.stats.sizes.k10_100}\n")
            f.write(f"100KB ~ <1MB: {self.stats.sizes.k100_1m}\n")
            f.write(f">= 1MB: {self.stats.sizes.ge1m}\n\n")

            f.write("Content Types\n=============\n")
            for ct in sorted(self.stats.by_content_type):
                f.write(f"{ct}: {self.stats.by_content_type[ct]}\n")

# --------- CLI
def main():
    ap = argparse.ArgumentParser(description="USC HW News Crawler (Python, async)")
    ap.add_argument("--site", choices=list(SEEDS.keys()), default="nytimes")
    ap.add_argument("--out", default="out")
    ap.add_argument("--max-pages", type=int, default=10000)   # MOD: 10k cap
    ap.add_argument("--depth", type=int, default=16)          # as in PDF
    ap.add_argument("--concurrency", type=int, default=7)     # multi-threading analogue
    ap.add_argument("--politeness-ms", type=int, default=200)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    crawler = Crawler(
    seed_url=SEEDS[args.site],
    out_dir=out_dir,
    site_key=args.site,
    max_pages=args.max_pages,
    max_depth=args.depth,
    concurrency=args.concurrency,
    politeness_ms=args.politeness_ms,
    )


    try:
        asyncio.run(crawler.run())
        print(f"Done. Outputs in: {out_dir.resolve()}")
    except KeyboardInterrupt:
        print("Interrupted.")
        try:
            asyncio.get_event_loop().run_until_complete(crawler.close())
        except Exception:
            pass

if __name__ == "__main__":
    main()
