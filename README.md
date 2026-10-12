# find\_top\_agents

A command-line tool to find and rank the top real estate agents or teams in a specified area by aggregating search engine results.

## Features

* Searches multiple query phrases to gather local agent listings
* Supports both **Serper.dev** (Google SERP API) and **Google Custom Search JSON API**
* Filters out aggregators, national brokerage corporate sites, directories, maps, and social media sites
* Extracts site titles from candidate pages (with search snippet fallback) and ranks by average position
* Outputs top N agents with detailed scoring metrics

## Requirements

* Python 3.8+
* See `requirements.txt` for Python dependencies (`requests`, `beautifulsoup4`)
* An API key for either **Serper.dev** or **Google Custom Search API**

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/brian-conrya/find_top_agents.git
   cd find_top_agents
   ```

2. (Optional) Create and activate a virtual environment:

   ```bash
   python3 -m venv env
   source env/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Copy `.env.example` to `.env` and configure your preferred provider:

```bash
cp .env.example .env
```

### Option 1: Serper.dev (Recommended - Fast setup)
1. Sign up at [serper.dev](https://serper.dev) and get your API key (2,500 free searches on signup).
2. Add to `.env`:
   ```bash
   SERPER_API_KEY=your_serper_api_key_here
   ```
   Or export in your terminal:
   ```bash
   export SERPER_API_KEY="your_serper_api_key_here"
   ```

### Option 2: Google Custom Search JSON API (Official)
1. Go to [Google Cloud Console](https://console.cloud.google.com/), enable the **Custom Search API**, and create an API Key.
2. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/), create an engine, and ensure **"Search the entire web"** is enabled. Copy the Search Engine ID (`cx`).
3. Add to `.env`:
   ```bash
   GOOGLE_API_KEY=your_google_cloud_api_key
   GOOGLE_CSE_ID=your_search_engine_cx_id
   ```
   Or export in your terminal:
   ```bash
   export GOOGLE_API_KEY="your_google_cloud_api_key"
   export GOOGLE_CSE_ID="your_search_engine_cx_id"
   ```

## Usage

Run the script with the desired area:

```bash
python find_top_agents.py "pittsburgh pa" -n 5 -r 50
```

**Options:**

* `area`: Area to search (e.g., `"pittsburgh pa"`).
* `-n, --top`: Number of top agents to display (default: 5).
* `-r, --results`: Number of search results to retrieve per query (default: 50).
* `--provider`: Search provider to use: `auto` (default), `serper`, or `google`.
* `--serper-key`: Pass Serper API key directly via CLI.
* `--google-key`: Pass Google API key directly via CLI.
* `--google-cx`: Pass Google Search Engine ID directly via CLI.

### Example

```text
$ python find_top_agents.py "pittsburgh" -n 1
INFO: Using search provider: serper
INFO: Searching query: best realtors in pittsburgh
INFO: Searching query: best real estate agents in pittsburgh
INFO: Searching query: best real estate agents pittsburgh
INFO: Searching query: best realtor in pittsburgh
INFO: Searching query: top realtors in pittsburgh
INFO: Searching query: top real estate agents in pittsburgh
INFO: Searching query: top real estate agents pittsburgh
INFO: Searching query: top pittsburgh realtors

Top 1 agents (lower total_score is better):

1. Top Real Estate Agent in Pittsburgh | Tarasa Hurley Team — https://www.tarasa.com/
    total_score=37, avg_rank=4.62, best_rank=3, worst_rank=5, appearances=8/8
```
