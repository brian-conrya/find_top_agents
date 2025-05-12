# find\_top\_agents

A command-line tool to find and rank the top real estate agents or teams in a specified area by aggregating Google search results.

## Features

* Searches multiple query phrases to gather agent listings
* Filters out aggregate, national brokerage, and social media sites
* Extracts site titles and ranks by average position
* Outputs top N agents with detailed scoring metrics

## Requirements

* Python 3.7+
* See `requirements.txt` for Python dependencies

## Installation

1. Clone the repository:

   git clone [https://github.com/brian-conrya/find\_top\_agents.git](https://github.com/brian-conrya/find_top_agents.git)
   cd find\_top\_agents

2. (Optional) Create and activate a virtual environment:

   python3 -m venv env
   source env/bin/activate

3. Install dependencies:

   pip install -r requirements.txt

## Usage

Run the script with the desired area and options:

python find\_top\_agents.py "pittsburgh pa" -n 5 -r 50

**Options:**

* `area`: Area to search (e.g., `"pittsburgh"`).
* `-n, --top`: Number of top agents to display (default: 5).
* `-r, --results`: Number of Google search results per query (default: 50).

### Example

```
$ python find_top_agents.py "pittsburgh" -n 1
INFO: Searching query: best realtors in pittsburgh
INFO: Searching query: best real estate agents in pittsburgh
INFO: Searching query: best real estate agents pittsburgh
INFO: Searching query: best realtor in pittsburgh
INFO: Searching query: top realtors in pittsburgh
INFO: Searching query: top real estate agents in pittsburgh
INFO: Searching query: top real estate agents pittsburgh
INFO: Searching query: top pittsburgh realtors
```
Top 1 agents (lower total_score is better):

1. Top Real Estate Agent in Pittsburgh | Tarasa Hurley Team — [https://www.tarasa.com/](https://www.tarasa.com/)
   total\_score=37, avg\_rank=4.62, best\_rank=3, worst\_rank=5, appearances=8/8
