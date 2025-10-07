# News Web Crawler

A professional asynchronous web crawler designed for crawling major news websites as part of USC's Information Retrieval and Web Search course.

## 🚀 Features

- **Asynchronous crawling** with configurable concurrency
- **Robots.txt compliance** for respectful crawling
- **Politeness delays** to avoid overwhelming servers
- **Domain-focused crawling** (stays within target news site)
- **Comprehensive logging** of all crawl attempts and results
- **Multiple output formats** (CSV files + detailed reports)
- **Support for major news sites** (NYTimes, WSJ, Fox News, USA Today, LA Times)

## 📋 Requirements

- Python 3.7+
- Required packages (install via pip):
  ```bash
  pip install aiohttp beautifulsoup4 pandas
  ```

## 🏃‍♂️ Quick Start

### Basic Usage
```bash
# Crawl NYTimes with default settings (10,000 pages, depth 16)
python crawler.py

# Crawl specific news site
python crawler.py --site foxnews

# Limit pages and depth
python crawler.py --site nytimes --max-pages 1000 --depth 3

# Adjust concurrency and politeness
python crawler.py --site wsj --concurrency 5 --politeness-ms 500
```

### Command Line Options
```bash
python crawler.py [OPTIONS]

Options:
  --site {nytimes,wsj,foxnews,usatoday,latimes}
                        News site to crawl (default: nytimes)
  --out OUT             Output directory (default: out)
  --max-pages MAX_PAGES Maximum pages to crawl (default: 10000)
  --depth DEPTH         Maximum crawl depth (default: 16)
  --concurrency CONCURRENCY
                        Number of concurrent requests (default: 7)
  --politeness-ms POLITENESS_MS
                        Delay between requests in milliseconds (default: 200)
```

## 📊 Output Files

The crawler generates the following files in the output directory:

### CSV Files
1. **`fetch_<site>.csv`** - Records every fetch attempt
   - Columns: `URL`, `Status`
   - Example: `fetch_nytimes.csv`

2. **`visit_<site>.csv`** - Successfully crawled pages
   - Columns: `URL`, `Size`, `#Outlinks`, `Content-Type`
   - Example: `visit_nytimes.csv`

3. **`urls_<site>.csv`** - All discovered URLs
   - Columns: `URL`, `Indicator` (OK/N_OK for in-domain/out-domain)
   - Example: `urls_nytimes.csv`

### Report File
4. **`CrawlReport_<site>.txt`** - Comprehensive crawl statistics
   - Fetch statistics (attempted, succeeded, failed)
   - Status code distribution
   - File size buckets
   - Content type distribution

## 📈 Sample Results

### NYTimes Crawl Results (Sample)
```
Name: XXXXXXXXX
News site crawled: nytimes

Fetch Statistics
=================
# fetches attempted: 9972
# fetches succeeded: 3529
# fetches failed or aborted: 6443

Outgoing URLs
==============
Total URLs extracted: 616081
# unique URLs extracted: 41275
# unique URLs within News Site: 37051
# unique URLs outside News Site: 4224

Status Codes
============
200: 3529
400: 3
403: 6333
404: 18
599: 89

File Sizes
==========
< 1KB: 1
1KB ~ <10KB: 1
10KB ~ <100KB: 49
100KB ~ <1MB: 3005
>= 1MB: 473

Content Types
==============
application/rss+xml: 1
application/xml: 7
text/csv: 2
text/html: 3518
```



## 🏗️ Architecture

### Key Components

1. **Crawler Class** - Main orchestrator
   - Manages URL queue and visited set
   - Coordinates multiple async workers
   - Handles CSV logging and statistics

2. **Politeness Controller** - Rate limiting
   - Enforces delays between requests
   - Uses async locks for thread safety

3. **Statistics Tracking** - Data collection
   - Monitors fetch attempts and successes
   - Categorizes file sizes and content types
   - Tracks HTTP status codes

4. **URL Processing** - Link extraction
   - Normalizes relative URLs to absolute
   - Filters non-HTTP links
   - Respects domain boundaries

### Async Design
- Uses `asyncio` for concurrent HTTP requests
- `aiohttp` for efficient async HTTP client
- `asyncio.Semaphore` for controlling concurrency
- `asyncio.Lock` for thread-safe operations

## 🤖 Robots.txt Compliance

The crawler automatically:
- Fetches and parses robots.txt files
- Respects crawl delays and restrictions
- Uses proper User-Agent identification
- Falls back gracefully if robots.txt is unavailable

## 🔍 Analysis Tools

### Jupyter Notebook (`stat.ipynb`)
- Loads and analyzes crawl results
- Generates comprehensive reports
- Provides data visualization capabilities
- Automatically updates crawl reports

### Usage
```bash
# Start Jupyter notebook
jupyter notebook stat.ipynb

# Or run specific analysis
python -c "exec(open('stat.ipynb').read())"
```

## 🛡️ Error Handling

The crawler includes robust error handling for:
- Network timeouts and connection errors
- Malformed URLs and HTML
- Robots.txt parsing failures
- CSV file write errors
- Keyboard interrupts (Ctrl+C)

## 📚 Technical Details

### HTTP Features
- Follows redirects automatically
- Respects Content-Type headers
- Implements proper timeouts (15 seconds)
- Uses custom User-Agent for identification

### URL Processing
- Converts relative URLs to absolute
- Removes URL fragments (#anchors)
- Filters out mailto: and javascript: links
- Validates HTTP/HTTPS schemes only

### Performance Optimizations
- Connection pooling via aiohttp sessions
- Efficient deque-based URL queue
- Set-based duplicate URL detection
- Minimal memory footprint for large crawls

## 🎯 Supported News Sites

| Site | URL | Default Available |
|------|-----|-------------------|
| NYTimes | https://www.nytimes.com/ | ✅ |
| Wall Street Journal | https://www.wsj.com/ | ✅ |
| Fox News | https://www.foxnews.com/ | ✅ |
| USA Today | https://www.usatoday.com/ | ✅ |
| LA Times | https://www.latimes.com/ | ✅ |

## 📝 Assignment Context

This crawler was developed for USC CSCI 572 (Information Retrieval and Web Search) course work. It demonstrates:

- Professional web crawling practices
- Asynchronous programming with Python
- HTTP protocol understanding
- Data collection and analysis
- Software engineering best practices

## 👨‍💻 Author

**Tianyu Zhang**  
Semester: Spring 2025

## 📄 License

This project is developed for educational purposes as part of USC coursework.

---

*For questions or issues, please refer to the course materials or contact the instructor.*
