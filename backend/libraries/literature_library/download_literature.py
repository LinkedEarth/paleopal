from __future__ import annotations

"""literature_library.download_literature

Download open-access PDFs for a given research topic from
  • Semantic Scholar (research articles)
  • DuckDuckGo PDF search (instructional material / syllabi)

Example:
    python -m literature_library.download_literature "paleoclimatology" --out pdfs --papers 100 --instructional 30
"""

import pathlib
import requests
import logging
import argparse
import urllib.parse
from typing import List, Dict, Optional, Tuple, Set
from tqdm import tqdm
import re
import os, time
from dataclasses import dataclass
from enum import Enum
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import hashlib
import json
from urllib.parse import urlparse, parse_qs

LOG = logging.getLogger("lit-dl")
logging.basicConfig(level=logging.INFO)

class SearchEngine(Enum):
    GOOGLE = "google"
    DUCKDUCKGO = "duckduckgo"

class PaperSource(Enum):
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CORE = "core"
    BASE = "base"
    UNPAYWALL = "unpaywall"
    ALL = "all"  # Search all sources

@dataclass
class SearchConfig:
    engine: SearchEngine
    api_key: Optional[str] = None
    search_engine_id: Optional[str] = None

@dataclass
class PaperInfo:
    title: str
    url: str
    source: PaperSource
    doi: Optional[str] = None
    authors: List[str] = None
    abstract: Optional[str] = None
    published_date: Optional[str] = None
    journal: Optional[str] = None
    keywords: List[str] = None
    citations: Optional[int] = None
    score: Optional[float] = None  # Relevance score if available

# API Keys and configuration
S2_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
CORE_API_KEY = os.getenv("CORE_API_KEY")
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL")  # Required for Unpaywall API

# Configure search engines
SEARCH_CONFIG = SearchConfig(
    engine=SearchEngine.GOOGLE if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID else SearchEngine.DUCKDUCKGO,
    api_key=GOOGLE_API_KEY,
    search_engine_id=GOOGLE_SEARCH_ENGINE_ID
)

# URLs
SEM_SCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_URL = "http://export.arxiv.org/api/query"
CORE_API_URL = "https://core.ac.uk/api/v3/search/works"
BASE_API_URL = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"
UNPAYWALL_API_URL = "https://api.unpaywall.org/v2"
CROSSREF_API_URL = "https://api.crossref.org/works"
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
DUCK_URL = "https://duckduckgo.com/html/"

# Headers
if S2_API_KEY:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "x-api-key": S2_API_KEY,
    }
else:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name)
    return name[:120]


def fetch_semantic_scholar(query: str, limit: int = 100, *, retries: int = 3) -> List[Dict[str, str]]:
    LOG.info("Querying Semantic Scholar for '%s'", query)
    params = {
        "query": query,
        "limit": str(limit),
        "fields": "title,openAccessPdf",
    }
    attempt = 0
    while True:
        attempt += 1
        resp = requests.get(SEM_SCH_URL, params=params, headers=HEADERS, timeout=30)
        if resp.status_code != 429:
            resp.raise_for_status()
            break
        if attempt > retries:
            raise RuntimeError("Semantic Scholar rate limit exceeded (HTTP 429)")
        wait = 30 * attempt
        LOG.warning("Semantic Scholar rate limited. Sleeping %s seconds (attempt %s/%s)", wait, attempt, retries)
        time.sleep(wait)
    data = resp.json()
    out = []
    for paper in data.get("data", []):
        pdf_info = paper.get("openAccessPdf") or {}
        url = pdf_info.get("url")
        if not url or not url.endswith(".pdf"):
            continue
        out.append({"title": paper.get("title", "paper"), "url": url})
    LOG.info("Semantic Scholar returned %d downloadable PDFs", len(out))
    return out


_INSTR_KEYWORDS = [
    "syllabus",
    "lecture notes",
    "course notes",
    "chapter pdf",
    "tutorial pdf",
    "lecture slides",
    "course material",
    "textbook chapter",
    "study guide",
    "handout",
]


def _extract_pdf_links(html: str) -> List[str]:
    """Extract PDF links from HTML using multiple patterns."""
    patterns = [
        r'href="(https?://[^\"]+\.pdf)"',  # Standard href pattern
        r'<a[^>]+href="(https?://[^\"]+\.pdf)"',  # Full anchor tag pattern
        r'https?://[^\s<>"]+\.pdf',  # Raw URL pattern
    ]
    links = set()
    for pattern in patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            # Clean and normalize the URL
            url = urllib.parse.unquote(match)
            if url.startswith('http'):
                links.add(url)
    return list(links)


def _ddg_pdf_links(search_term: str) -> List[str]:
    """Search DuckDuckGo for PDF links with improved error handling."""
    params = {
        "q": f"{search_term} filetype:pdf",
        "kl": "wt-wt",  # Region: worldwide
        "kad": "en_US",  # Language: English
    }
    try:
        resp = requests.get(
            DUCK_URL,
            params=params,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True
        )
        resp.raise_for_status()
        
        # Log the response for debugging
        LOG.debug("DuckDuckGo response status: %d", resp.status_code)
        LOG.debug("DuckDuckGo response headers: %s", dict(resp.headers))
        
        if "captcha" in resp.text.lower() or "bot" in resp.text.lower():
            LOG.warning("DuckDuckGo detected automated access. Consider using a different search engine.")
            return []
            
        links = _extract_pdf_links(resp.text)
        LOG.debug("Found %d PDF links for search term: %s", len(links), search_term)
        return links
        
    except requests.exceptions.RequestException as e:
        LOG.error("DuckDuckGo request failed: %s", str(e))
        return []
    except Exception as e:
        LOG.error("Unexpected error during DuckDuckGo search: %s", str(e))
        return []


def _google_search_pdfs(query: str, limit: int = 30) -> List[str]:
    """Search for PDFs using Google Custom Search API."""
    if not SEARCH_CONFIG.api_key or not SEARCH_CONFIG.search_engine_id:
        LOG.warning("Google Search API not configured. Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID environment variables.")
        return []

    params = {
        "key": SEARCH_CONFIG.api_key,
        "cx": SEARCH_CONFIG.search_engine_id,
        "q": f"{query} filetype:pdf",
        "num": min(limit, 10),  # Google CSE allows max 10 results per request
        "safe": "off",
    }

    all_links = []
    start_index = 1

    while len(all_links) < limit:
        try:
            params["start"] = start_index
            resp = requests.get(GOOGLE_SEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "items" not in data:
                break

            for item in data["items"]:
                link = item.get("link", "")
                if link.lower().endswith(".pdf"):
                    all_links.append(link)
                    if len(all_links) >= limit:
                        break

            if "queries" in data and "nextPage" in data["queries"]:
                start_index += len(data["items"])
            else:
                break

            # Respect Google's rate limits
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            LOG.error("Google Search API request failed: %s", str(e))
            break
        except Exception as e:
            LOG.error("Unexpected error during Google search: %s", str(e))
            break

    LOG.info("Google Search found %d PDF links", len(all_links))
    return all_links


def fetch_instructional_pdfs(query: str, limit: int = 30) -> List[str]:
    """Fetch instructional PDFs using configured search engine."""
    unique_links: List[str] = []
    seen = set()

    # Prepare search terms
    search_terms = [query] + [f"{query} {kw}" for kw in _INSTR_KEYWORDS]

    for term in search_terms:
        if len(unique_links) >= limit:
            break

        LOG.info("Searching for: %s", term)
        
        # Try Google Search first if configured
        if SEARCH_CONFIG.engine == SearchEngine.GOOGLE:
            links = _google_search_pdfs(term, limit=limit - len(unique_links))
        else:
            # Fallback to DuckDuckGo
            links = _ddg_pdf_links(term)

        for link in links:
            link = urllib.parse.unquote(link)
            if link in seen:
                continue
            seen.add(link)
            unique_links.append(link)
            if len(unique_links) >= limit:
                break

        # Add a small delay between requests
        time.sleep(2)

    LOG.info("Collected %d instructional PDF links", len(unique_links))
    return unique_links


def fetch_arxiv_papers(query: str, limit: int = 100, *, retries: int = 3) -> List[PaperInfo]:
    """Fetch papers from arXiv API."""
    LOG.info("Querying arXiv for '%s'", query)
    
    # arXiv API parameters
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit, 100),  # arXiv API limit is 100 per request
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    
    papers = []
    attempt = 0
    
    while len(papers) < limit and attempt < retries:
        try:
            resp = requests.get(ARXIV_API_URL, params=params, timeout=30)
            resp.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(resp.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}
            
            entries = root.findall('.//atom:entry', ns)
            if not entries:
                break
                
            for entry in entries:
                if len(papers) >= limit:
                    break
                    
                # Extract paper info
                title = entry.find('atom:title', ns).text.strip()
                abstract = entry.find('atom:summary', ns).text.strip()
                published = entry.find('atom:published', ns).text
                
                # Get PDF URL (replace abs with pdf in the id)
                pdf_url = entry.find('atom:id', ns).text.replace('/abs/', '/pdf/') + '.pdf'
                
                # Get authors
                authors = [author.find('atom:name', ns).text 
                          for author in entry.findall('atom:author', ns)]
                
                papers.append(PaperInfo(
                    title=title,
                    url=pdf_url,
                    source=PaperSource.ARXIV,
                    authors=authors,
                    abstract=abstract,
                    published_date=published
                ))
            
            # Update start index for next batch
            params["start"] += len(entries)
            
            # Respect arXiv's rate limit (1 request per second)
            time.sleep(3)
            
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt >= retries:
                LOG.error("arXiv API request failed after %d attempts: %s", retries, str(e))
                break
            wait = 5 * attempt
            LOG.warning("arXiv API request failed, retrying in %d seconds (attempt %d/%d)", 
                       wait, attempt, retries)
            time.sleep(wait)
        except Exception as e:
            LOG.error("Unexpected error during arXiv search: %s", str(e))
            break
    
    LOG.info("arXiv returned %d papers", len(papers))
    return papers


def _get_core_papers(query: str, limit: int = 100) -> List[PaperInfo]:
    """Fetch papers from CORE API."""
    if not CORE_API_KEY:
        LOG.warning("CORE API key not set. Set CORE_API_KEY environment variable.")
        return []

    LOG.info("Querying CORE for '%s'", query)
    papers = []
    offset = 0
    batch_size = min(limit, 100)  # CORE API limit is 100 per request

    while len(papers) < limit:
        try:
            params = {
                "q": query,
                "limit": batch_size,
                "offset": offset,
                "metadata": "true",
                "fulltext": "true",
                "citations": "true",
                "references": "true",
                "similar": "true",
                "duplicate": "false",
                "urls": "true",
                "raw": "true",
                "apiKey": CORE_API_KEY
            }
            
            resp = requests.get(CORE_API_URL, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if not data.get("results"):
                break
                
            for result in data["results"]:
                if len(papers) >= limit:
                    break
                    
                # Get PDF URL
                pdf_url = None
                for url in result.get("downloadUrl", []):
                    if url.lower().endswith(".pdf"):
                        pdf_url = url
                        break
                        
                if not pdf_url:
                    continue
                    
                papers.append(PaperInfo(
                    title=result.get("title", "Untitled"),
                    url=pdf_url,
                    source=PaperSource.CORE,
                    doi=result.get("doi"),
                    authors=[author.get("name") for author in result.get("authors", [])],
                    abstract=result.get("abstract"),
                    published_date=result.get("publishedDate"),
                    journal=result.get("publisher"),
                    keywords=result.get("topics", []),
                    citations=result.get("citedByCount"),
                    score=result.get("relevanceScore")
                ))
                
            offset += batch_size
            time.sleep(1)  # Respect rate limit
            
        except Exception as e:
            LOG.error("CORE API request failed: %s", str(e))
            break
            
    LOG.info("CORE returned %d papers", len(papers))
    return papers


def _get_base_papers(query: str, limit: int = 100) -> List[PaperInfo]:
    """Fetch papers from BASE API."""
    LOG.info("Querying BASE for '%s'", query)
    papers = []
    offset = 0
    batch_size = min(limit, 50)  # BASE API limit is 50 per request

    while len(papers) < limit:
        try:
            params = {
                "func": "PerformSearch",
                "query": f"{query} filetype:pdf",
                "format": "json",
                "hits": batch_size,
                "offset": offset
            }
            
            resp = requests.get(BASE_API_URL, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if not data.get("response", {}).get("docs"):
                break
                
            for doc in data["response"]["docs"]:
                if len(papers) >= limit:
                    break
                    
                # Get PDF URL
                pdf_url = None
                for link in doc.get("link", []):
                    if link.lower().endswith(".pdf"):
                        pdf_url = link
                        break
                        
                if not pdf_url:
                    continue
                    
                papers.append(PaperInfo(
                    title=doc.get("title", ["Untitled"])[0],
                    url=pdf_url,
                    source=PaperSource.BASE,
                    doi=doc.get("doi", [None])[0],
                    authors=doc.get("author", []),
                    abstract=doc.get("abstract", [None])[0],
                    published_date=doc.get("year", [None])[0],
                    journal=doc.get("publisher", [None])[0],
                    keywords=doc.get("subject", [])
                ))
                
            offset += batch_size
            time.sleep(1)  # Respect rate limit
            
        except Exception as e:
            LOG.error("BASE API request failed: %s", str(e))
            break
            
    LOG.info("BASE returned %d papers", len(papers))
    return papers


def _get_unpaywall_papers(query: str, limit: int = 100) -> List[PaperInfo]:
    """Fetch papers from Unpaywall API."""
    if not UNPAYWALL_EMAIL:
        LOG.warning("Unpaywall email not set. Set UNPAYWALL_EMAIL environment variable.")
        return []

    LOG.info("Querying Unpaywall for '%s'", query)
    papers = []
    
    # First get DOIs from Crossref
    try:
        params = {
            "query": query,
            "rows": limit,
            "mailto": UNPAYWALL_EMAIL
        }
        
        resp = requests.get(CROSSREF_API_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        for item in data.get("message", {}).get("items", []):
            if len(papers) >= limit:
                break
                
            doi = item.get("DOI")
            if not doi:
                continue
                
            # Get open access URL from Unpaywall
            unpaywall_url = f"{UNPAYWALL_API_URL}/{doi}?email={UNPAYWALL_EMAIL}"
            try:
                resp = requests.get(unpaywall_url, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                paper_data = resp.json()
                
                if not paper_data.get("best_oa_location", {}).get("url"):
                    continue
                    
                papers.append(PaperInfo(
                    title=item.get("title", ["Untitled"])[0],
                    url=paper_data["best_oa_location"]["url"],
                    source=PaperSource.UNPAYWALL,
                    doi=doi,
                    authors=[author.get("given", "") + " " + author.get("family", "") 
                            for author in item.get("author", [])],
                    abstract=item.get("abstract"),
                    published_date=item.get("published", {}).get("date-parts", [[None]])[0][0],
                    journal=item.get("container", {}).get("title"),
                    citations=item.get("is-referenced-by-count")
                ))
                
            except Exception as e:
                LOG.debug("Failed to get Unpaywall data for DOI %s: %s", doi, str(e))
                continue
                
            time.sleep(1)  # Respect rate limit
            
    except Exception as e:
        LOG.error("Unpaywall/Crossref API request failed: %s", str(e))
        
    LOG.info("Unpaywall returned %d papers", len(papers))
    return papers


def _deduplicate_papers(papers: List[PaperInfo]) -> List[PaperInfo]:
    """Remove duplicate papers based on title similarity and DOI."""
    seen_dois: Set[str] = set()
    seen_titles: Set[str] = set()
    unique_papers: List[PaperInfo] = []
    
    def normalize_title(title: str) -> str:
        """Normalize title for comparison."""
        return " ".join(title.lower().split())
    
    for paper in papers:
        # Skip if we've seen this DOI
        if paper.doi and paper.doi in seen_dois:
            continue
            
        # Skip if we've seen a very similar title
        norm_title = normalize_title(paper.title)
        if norm_title in seen_titles:
            continue
            
        seen_dois.add(paper.doi) if paper.doi else None
        seen_titles.add(norm_title)
        unique_papers.append(paper)
        
    return unique_papers


def fetch_research_papers(query: str, limit: int = 100, source: PaperSource = PaperSource.ALL) -> List[PaperInfo]:
    """Fetch research papers from the specified source(s)."""
    all_papers: List[PaperInfo] = []
    
    if source == PaperSource.ALL:
        sources = [PaperSource.ARXIV, PaperSource.CORE, PaperSource.BASE, PaperSource.UNPAYWALL]
    else:
        sources = [source]
        
    for src in sources:
        if len(all_papers) >= limit:
            break
            
        try:
            if src == PaperSource.ARXIV:
                papers = fetch_arxiv_papers(query, limit=limit - len(all_papers))
            elif src == PaperSource.CORE:
                papers = _get_core_papers(query, limit=limit - len(all_papers))
            elif src == PaperSource.BASE:
                papers = _get_base_papers(query, limit=limit - len(all_papers))
            elif src == PaperSource.UNPAYWALL:
                papers = _get_unpaywall_papers(query, limit=limit - len(all_papers))
            elif src == PaperSource.SEMANTIC_SCHOLAR:
                papers = fetch_semantic_scholar(query, limit=limit - len(all_papers))
                papers = [PaperInfo(
                    title=p["title"],
                    url=p["url"],
                    source=PaperSource.SEMANTIC_SCHOLAR
                ) for p in papers]
            else:
                continue
                
            all_papers.extend(papers)
            
        except Exception as e:
            LOG.error("Failed to fetch papers from %s: %s", src.value, str(e))
            continue
            
    # Deduplicate papers
    unique_papers = _deduplicate_papers(all_papers)
    
    # Sort by source priority and limit
    source_priority = {
        PaperSource.ARXIV: 0,
        PaperSource.CORE: 1,
        PaperSource.BASE: 2,
        PaperSource.UNPAYWALL: 3,
        PaperSource.SEMANTIC_SCHOLAR: 4
    }
    
    unique_papers.sort(key=lambda p: (source_priority.get(p.source, 999), p.score or 0), reverse=True)
    return unique_papers[:limit]


def download_file(url: str, dest: pathlib.Path, paper_info: Optional[PaperInfo] = None):
    """Download a file with improved error handling and metadata saving."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Create metadata file path
    meta_dest = dest.with_suffix('.json')
    
    try:
        with requests.get(url, stream=True, headers=HEADERS, timeout=40) as r:
            r.raise_for_status()
            
            # Check if it's actually a PDF
            content_type = r.headers.get('content-type', '').lower()
            if not content_type.startswith('application/pdf'):
                LOG.warning("URL %s returned non-PDF content type: %s", url, content_type)
                return False
                
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            # Save metadata if available
            if paper_info:
                meta = {
                    "title": paper_info.title,
                    "url": url,
                    "source": paper_info.source.value,
                    "download_date": datetime.now().isoformat(),
                }
                if paper_info.authors:
                    meta["authors"] = paper_info.authors
                if paper_info.abstract:
                    meta["abstract"] = paper_info.abstract
                if paper_info.published_date:
                    meta["published_date"] = paper_info.published_date
                    
                with meta_dest.open('w') as f:
                    json.dump(meta, f, indent=2)
                    
            return True
            
    except requests.exceptions.RequestException as e:
        LOG.warning("Failed to download %s: %s", url, e)
        return False
    except Exception as e:
        LOG.warning("Unexpected error downloading %s: %s", url, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Download literature PDFs for a topic")
    parser.add_argument("topic", help="Search topic, e.g. 'paleoclimatology'")
    parser.add_argument("--out", default="literature_pdfs", help="Output directory")
    parser.add_argument("--papers", type=int, default=100, help="Max research PDFs")
    parser.add_argument("--instructional", type=int, default=30, help="Max instructional PDFs")
    parser.add_argument("--search-engine", choices=[e.value for e in SearchEngine], 
                       default=SEARCH_CONFIG.engine.value,
                       help="Search engine to use for instructional PDFs")
    parser.add_argument("--paper-source", choices=[s.value for s in PaperSource],
                       default=PaperSource.ALL.value,
                       help="Source for research papers")
    args = parser.parse_args()

    # Update search engine if specified
    if args.search_engine != SEARCH_CONFIG.engine.value:
        if args.search_engine == SearchEngine.GOOGLE.value and not (GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID):
            LOG.error("Google Search API not configured. Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID environment variables.")
            return
        SEARCH_CONFIG.engine = SearchEngine(args.search_engine)

    out_dir = pathlib.Path(args.out)
    papers_dir = out_dir / "papers"
    instr_dir = out_dir / "instructional"

    # Research papers
    paper_source = PaperSource(args.paper_source)
    papers = fetch_research_papers(args.topic, limit=args.papers, source=paper_source)
    
    # Log sources of found papers
    source_counts = {}
    for paper in papers:
        source_counts[paper.source.value] = source_counts.get(paper.source.value, 0) + 1
    LOG.info("Found papers by source: %s", json.dumps(source_counts, indent=2))
    
    for paper in tqdm(papers, desc="Downloading papers"):
        fname = _safe_filename(paper.title) + ".pdf"
        dest = papers_dir / fname
        if dest.exists():
            continue
        download_file(paper.url, dest, paper_info=paper)

    # Instructional PDFs
    instr_links = fetch_instructional_pdfs(args.topic, limit=args.instructional)
    for url in tqdm(instr_links, desc="Downloading instructional"):
        fname = _safe_filename(pathlib.Path(urllib.parse.urlparse(url).path).stem) + ".pdf"
        dest = instr_dir / fname
        if dest.exists():
            continue
        download_file(url, dest)

    LOG.info("Download complete → %s", out_dir)


if __name__ == "__main__":
    main() 