#!/usr/bin/env python3
"""
This script searches Google for organic pages about the best real estate agents or teams
in a given area by executing multiple query phrases individually. It then visits each page,
heuristically extracts the agent or team name from the title, and filters out pages from unwanted domains such as aggregate
sites, national brokerages, maps, sponsored ads, etc.
Finally, it aggregates the results by summing the ranking positions from each query (using a
penalty for missing appearances) and returns the top N (or fewer if not enough results).

Usage:
    python find_top_agents.py "pittsburgh pa" [-n TOP_COUNT] [-r RESULTS_COUNT]

Optional arguments:
    -n, --top      Number of top agent/team pages to extract (default is 5).
    -r, --results  Number of search results to retrieve per query (default is 50).
"""

import argparse
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

import requests
from bs4 import BeautifulSoup
from googlesearch import search
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration & Constants ---
BANNED_KEYWORDS = {
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
    "/news/",
    "/money/",
    "/business/",
    "seolium",
    "agentpronto",
    "upnest",
    "housecashin",
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


def make_session() -> requests.Session:
    """Create an HTTP session with retry logic and a custom User-Agent."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def is_banned_url(url: str) -> bool:
    """Return True if the URL should be ignored based on banned keywords or maps."""
    u = url.lower()
    if GOOGLE_MAPS in u:
        return True
    return any(keyword in u for keyword in BANNED_KEYWORDS)


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


def get_search_results(query: str, num: int) -> List[str]:
    """Run a Google search and return a list of result URLs (or empty list on error)."""
    try:
        return list(search(query, region="us", num_results=num, sleep_interval=2))
    except Exception as e:
        logger.error("Search failed for %r: %s", query, e)
        return []


def fetch_agents_for_query(
    session: requests.Session, query: str, max_results: int
) -> Dict[str, AgentEntry]:
    """Fetch search results for a single query and return a dict of agent_key to AgentEntry."""
    logger.info("Searching query: %s", query)
    entries: Dict[str, AgentEntry] = {}

    for rank, url in enumerate(get_search_results(query, max_results), start=1):
        if is_banned_url(url):
            continue
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.debug("Failed to fetch %s: %s", url, e)
            continue

        title = extract_meta_title(resp.text)
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
        description="Find top real estate agents/teams in a given area."
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
    args = parser.parse_args()

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
    query_results = [fetch_agents_for_query(session, q, args.results) for q in queries]

    # Aggregate and sort
    aggregated = aggregate_entries(query_results, penalty)

    # Display top N with average rank
    num_queries = len(queries)
    n = min(args.top, len(aggregated))
    print(f"Top {n} agents (lower total_score is better):")
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
