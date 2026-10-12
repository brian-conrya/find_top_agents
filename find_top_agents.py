#!/usr/bin/env python3
"""
This script searches for organic pages about the best real estate agents or teams
in a given area by executing multiple query phrases individually. It visits candidate pages,
heuristically extracts the agent or team name from the title, filters out unwanted domains
such as aggregators, national brokerages, maps, directories, and social media sites,
and aggregates ranking positions across queries.

Supported search providers:
  1. Serper.dev (Google SERP API - set SERPER_API_KEY)
  2. Google Custom Search JSON API (set GOOGLE_API_KEY and GOOGLE_CSE_ID)

Usage:
    python find_top_agents.py "pittsburgh pa" [-n TOP_COUNT] [-r RESULTS_COUNT] [--provider {auto,serper,google}]

Optional arguments:
    -n, --top          Number of top agent/team pages to extract (default is 5).
    -r, --results      Number of search results to retrieve per query (default is 50).
    --provider         Search provider: 'auto' (default), 'serper', or 'google'.
    --serper-key       Serper.dev API key (or set SERPER_API_KEY env var).
    --google-key       Google Cloud API key (or set GOOGLE_API_KEY env var).
    --google-cx        Google Custom Search Engine ID (or set GOOGLE_CSE_ID env var).
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration & Constants ---
SKIPPED_KEYWORDS = {
    "zillow",
    "trulia",
    "redfin",
    "realtor.com",
    "usnews",
    "city-data",
    "yelp",
    "fastexpert",
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "x.com",
    "reddit",
    "fivestarprofessional",
    "realtrends",
    "houzeo",
    "effectiveagents",
    "nextdoor",
    "expertise",
    "homelight",
    "homeguide",
    "nar.realtor",
    "youtube",
    "thumbtack",
    "topagentmagazine",
    "yellowpages",
    "triple",
    "angi",
    "listwithclever",
    "tiktok",
    "movoto",
    ".org",
    "experience.com",
    "bankrate",
    "expertise.com",
    "glassdoor",
    "biggerpockets",
    "agentproto",
    "landsearch",
    "coldwellbanker",
    "remax",
    "sothebys",
    "bhhs",
    "kellerwilliams",
    "kw.com",
    "century21",
    "c21",
    "bhgre",
    "era.com",
    "elliman",
    "compass",
    "exprealty",
    "corcoran",
    "weichert",
    "howardhanna",
    "longandfoster",
    "realtyexecutives",
    "realtyonegroup",
    "homesmart",
    "exitrealty",
    "ratemyagent",
    "sulekha",
    "bizjournals",
    "news/",
    "money/",
    "business/",
    "directory/",
    "seolium",
    "agentpronto",
    "upnest",
    "housecashin",
    "land.com",
    "rankmyagent.com",
}
AGENT_INDICATORS = [
    "realtor",
    "real estate agent",
    "team",
    "realty",
    "broker",
]
GOOGLE_MAPS = "google.com/maps"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.10 Safari/605.1.1"
)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class AgentEntry:
    name: str
    url: str
    rank: int


@dataclass
class AggregatedEntry:
    name: str
    url: str
    total_score: int
    best_rank: int
    worst_rank: int
    appearance_count: int


def load_dotenv(filepath: Optional[str] = None) -> None:
    """Load key-value pairs from a .env file into os.environ if not already present."""
    candidates = []
    if filepath:
        candidates.append(filepath)
    else:
        # Check current working directory, then script directory
        candidates.append(os.path.join(os.getcwd(), ".env"))
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(script_dir, ".env"))

    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
                break
            except Exception as e:
                logger.debug("Failed reading .env from %s: %s", path, e)


def make_session() -> requests.Session:
    """Create an HTTP session with retry logic and a custom User-Agent."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def is_skipped_url(url: str) -> bool:
    """Return True if the URL should be ignored based on skipped keywords or maps."""
    u = url.lower()
    if GOOGLE_MAPS in u:
        return True
    return any(keyword in u for keyword in SKIPPED_KEYWORDS)


def extract_meta_title(html: str) -> Optional[str]:
    """
    Extracts the meta title from HTML content, checking og:title,
    then <meta name="title">, then falling back to <title>.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Open Graph
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    # <meta name="title">
    meta = soup.find("meta", attrs={"name": "title"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    # <title>
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def looks_like_agent(title: str) -> bool:
    """Return True if the title contains any agent/team indicator."""
    lower = title.lower()
    return any(indicator in lower for indicator in AGENT_INDICATORS)


class SearchAuthError(Exception):
    """Raised when search provider credentials fail authentication."""
    pass


def search_serper(query: str, num: int, api_key: str) -> List[Tuple[str, str]]:
    """
    Search using Serper.dev Google SERP API.
    Returns a list of (url, title) tuples.
    """
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": min(max(num, 10), 100),
        "gl": "us",
        "hl": "en",
    }
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=15,
        )
        if resp.status_code in (401, 403):
            raise SearchAuthError(
                f"Serper API authentication error (HTTP {resp.status_code}). Check your SERPER_API_KEY."
            )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic", []):
            link = item.get("link")
            title = item.get("title", "")
            if link:
                results.append((link, title))
        return results[:num]
    except SearchAuthError:
        raise
    except Exception as e:
        logger.error("Serper search failed for %r: %s", query, e)
        return []


def search_google_cse(query: str, num: int, api_key: str, cse_id: str) -> List[Tuple[str, str]]:
    """
    Search using Google Custom Search JSON API.
    Returns a list of (url, title) tuples.
    """
    results: List[Tuple[str, str]] = []
    max_to_fetch = min(max(num, 1), 100)

    for start in range(1, max_to_fetch + 1, 10):
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "gl": "us",
            "hl": "en",
            "start": start,
            "num": min(10, max_to_fetch - len(results)),
        }
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=15,
            )
            if resp.status_code in (400, 401, 403):
                raise SearchAuthError(
                    f"Google Custom Search API error: {resp.text} (HTTP {resp.status_code}). Check your GOOGLE_API_KEY and GOOGLE_CSE_ID."
                )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                link = item.get("link")
                title = item.get("title", "")
                if link:
                    results.append((link, title))
            if len(items) < params["num"]:
                break
        except SearchAuthError:
            raise
        except Exception as e:
            logger.error("Google CSE search failed for %r: %s", query, e)
            break

    return results[:num]


def get_search_results(
    query: str,
    num: int,
    provider: str,
    serper_key: Optional[str] = None,
    google_key: Optional[str] = None,
    google_cx: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """
    Dispatch query to the configured search provider.
    Returns a list of (url, title) tuples.
    """
    if provider == "serper":
        return search_serper(query, num, serper_key or "")
    elif provider == "google":
        return search_google_cse(query, num, google_key or "", google_cx or "")
    else:
        logger.error("Unsupported search provider: %r", provider)
        return []


def fetch_agents_for_query(
    session: requests.Session,
    query: str,
    max_results: int,
    provider: str,
    serper_key: Optional[str] = None,
    google_key: Optional[str] = None,
    google_cx: Optional[str] = None,
) -> Dict[str, AgentEntry]:
    """Fetch search results for a single query and return a dict of agent_key to AgentEntry."""
    logger.info("Searching query: %s", query)
    entries: Dict[str, AgentEntry] = {}

    search_items = get_search_results(
        query=query,
        num=max_results,
        provider=provider,
        serper_key=serper_key,
        google_key=google_key,
        google_cx=google_cx,
    )

    for rank, (url, serp_title) in enumerate(search_items, start=1):
        if is_skipped_url(url):
            continue

        title = None
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            title = extract_meta_title(resp.text)
        except Exception as e:
            logger.debug("Failed to fetch %s: %s", url, e)

        # Fall back to title from search engine if direct site fetch failed or had no title
        if not title:
            title = serp_title

        if not title or not looks_like_agent(title):
            continue

        key = title.lower()
        if key in entries:
            entries[key].rank = min(entries[key].rank, rank)
        else:
            entries[key] = AgentEntry(name=title, url=url, rank=rank)
            logger.debug("Found agent: %s at rank %d", title, rank)

    return entries


def aggregate_entries(
    query_results: List[Dict[str, AgentEntry]], penalty: int
) -> List[AggregatedEntry]:
    """Aggregate multiple query result dicts into a scored list of AggregatedEntry."""
    all_keys = set().union(*query_results)
    aggregated: List[AggregatedEntry] = []

    for key in all_keys:
        ranks: List[int] = []
        appearances = 0
        for qr in query_results:
            if key in qr:
                r = qr[key].rank
                ranks.append(r)
                appearances += 1
            else:
                ranks.append(penalty)

        total = sum(ranks)
        best = min(ranks)
        worst = max(ranks)
        # pick a representative entry (the one with the best rank)
        best_entry = min(
            (qr[key] for qr in query_results if key in qr), key=lambda e: e.rank
        )

        aggregated.append(
            AggregatedEntry(
                name=best_entry.name,
                url=best_entry.url,
                total_score=total,
                best_rank=best,
                worst_rank=worst,
                appearance_count=appearances,
            )
        )

    return sorted(aggregated, key=lambda e: e.total_score)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find top real estate agents/teams in a given area by aggregating search rankings."
    )
    parser.add_argument("area", help="Area to search (e.g., 'pittsburgh pa').")
    parser.add_argument(
        "-n",
        "--top",
        type=int,
        default=5,
        help="Number of top agent/team pages to extract (default is 5).",
    )
    parser.add_argument(
        "-r",
        "--results",
        type=int,
        default=50,
        help="Number of search results to retrieve per query (default is 50).",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "serper", "google"],
        default="auto",
        help="Search provider: 'auto' (default), 'serper', or 'google'.",
    )
    parser.add_argument(
        "--serper-key",
        help="Serper.dev API key (or set SERPER_API_KEY environment variable).",
    )
    parser.add_argument(
        "--google-key",
        help="Google Cloud API key (or set GOOGLE_API_KEY environment variable).",
    )
    parser.add_argument(
        "--google-cx",
        help="Google Custom Search Engine ID (or set GOOGLE_CSE_ID environment variable).",
    )
    args = parser.parse_args()

    # Load .env if present
    load_dotenv()

    # Resolve credentials
    serper_key = args.serper_key or os.getenv("SERPER_API_KEY")
    google_key = args.google_key or os.getenv("GOOGLE_API_KEY")
    google_cx = args.google_cx or os.getenv("GOOGLE_CSE_ID")

    provider = args.provider
    if provider == "auto":
        if serper_key:
            provider = "serper"
        elif google_key and google_cx:
            provider = "google"
        else:
            print(
                "\n"
                "====================================================================\n"
                "Error: No search provider API key configured.\n"
                "====================================================================\n"
                "Direct Google Search HTML scraping without an API is no longer supported.\n"
                "Please configure one of the supported search providers:\n\n"
                "Option 1: Serper.dev (Fastest setup, 2,500 free queries)\n"
                "  1. Sign up at https://serper.dev and copy your API key\n"
                "  2. Set the environment variable:\n"
                "       export SERPER_API_KEY=\"your_key_here\"\n"
                "     or pass: --serper-key \"your_key_here\"\n\n"
                "Option 2: Google Custom Search JSON API (Official, 100 free queries/day)\n"
                "  1. Enable 'Custom Search API' in Google Cloud Console to get an API key\n"
                "  2. Create a Search Engine at https://programmablesearchengine.google.com\n"
                "     (make sure 'Search the entire web' is turned ON) to get your CX ID\n"
                "  3. Set the environment variables:\n"
                "       export GOOGLE_API_KEY=\"your_api_key\"\n"
                "       export GOOGLE_CSE_ID=\"your_cx_id\"\n"
                "     or pass: --google-key \"...\" --google-cx \"...\"\n\n"
                "Tip: You can also copy .env.example to .env and put your keys there.\n"
                "====================================================================\n",
                file=sys.stderr,
            )
            sys.exit(1)
    elif provider == "serper" and not serper_key:
        logger.error("Provider 'serper' selected but SERPER_API_KEY is not set.")
        sys.exit(1)
    elif provider == "google" and (not google_key or not google_cx):
        logger.error("Provider 'google' selected but GOOGLE_API_KEY or GOOGLE_CSE_ID is not set.")
        sys.exit(1)

    logger.info("Using search provider: %s", provider)

    area = args.area.strip()
    queries = [
        f"best realtors in {area}",
        f"best real estate agents in {area}",
        f"best real estate agents {area}",
        f"best realtor in {area}",
        f"top realtors in {area}",
        f"top real estate agents in {area}",
        f"top real estate agents {area}",
        f"top {area} realtors",
    ]
    penalty = args.results + 1
    session = make_session()

    # Fetch, filter, and score each query
    try:
        query_results = [
            fetch_agents_for_query(
                session=session,
                query=q,
                max_results=args.results,
                provider=provider,
                serper_key=serper_key,
                google_key=google_key,
                google_cx=google_cx,
            )
            for q in queries
        ]
    except SearchAuthError as e:
        logger.error("%s", e)
        sys.exit(1)

    # Aggregate and sort
    aggregated = aggregate_entries(query_results, penalty)

    # Display top N with average rank
    num_queries = len(queries)
    n = min(args.top, len(aggregated))
    print(f"\nTop {n} agents (lower total_score is better):")
    for idx, ent in enumerate(aggregated[:n], start=1):
        avg_rank = ent.total_score / num_queries
        print(
            f"{idx}. {ent.name} — {ent.url}\n"
            f"    total_score={ent.total_score}, avg_rank={avg_rank:.2f}, "
            f"best_rank={ent.best_rank}, worst_rank={ent.worst_rank}, "
            f"appearances={ent.appearance_count}/{num_queries}"
        )


if __name__ == "__main__":
    main()
