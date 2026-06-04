#!/usr/bin/env python3
"""
Generate SVG stats for GitHub profile README.
Optimized for speed with parallel processing and caching.
"""

import os
import json
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import yaml

from ext_to_lang import ext_to_lang, EXCLUDED_LANGS

# Configuration
CONFIG_PATH = Path(".github/config/tracked-repos.yml")
STATS_DIR = Path(".github/stats")
CACHE_FILE = Path(".github/.stats_cache.json")
USERNAME = "SyntaxError4Life"
HF_USERNAME = "Logikisto"
EMAIL = "lilian@zanomega.com"

# API endpoints
GITHUB_GRAPHQL = "https://api.github.com/graphql"
HF_API = "https://huggingface.co/api"


def load_cache():
    """Load cache of processed commits."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Save cache of processed commits."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)


def run_graphql(query, variables=None):
    """Execute GraphQL query with token."""
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Content-Type": "application/json"
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    response = requests.post(GITHUB_GRAPHQL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def get_user_repos():
    """Get all public repos owned by user."""
    query = """
    query($username: String!, $cursor: String) {
        user(login: $username) {
            repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    nameWithOwner
                    defaultBranchRef {
                        name
                    }
                }
            }
        }
    }
    """
    
    repos = []
    cursor = None
    
    while True:
        result = run_graphql(query, {"username": USERNAME, "cursor": cursor})
        data = result["data"]["user"]["repositories"]
        repos.extend([n["nameWithOwner"] for n in data["nodes"]])
        
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    
    return repos


def get_contribution_calendar():
    """Get contribution calendar for last 12 months."""
    from datetime import datetime, timedelta
    
    # Date il y a 12 mois
    to_date = datetime.now()
    from_date = to_date - timedelta(days=365)
    
    from_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $username) {
            contributionsCollection(from: $from, to: $to) {
                contributionCalendar {
                    totalContributions
                    weeks {
                        contributionDays {
                            contributionCount
                            date
                        }
                    }
                }
            }
        }
    }
    """
    
    result = run_graphql(query, {
        "username": USERNAME,
        "from": from_str,
        "to": to_str
    })
    return result["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def calculate_streak(calendar):
    """Calculate current and longest streak from calendar."""
    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])
    
    # Sort by date
    days.sort(key=lambda x: x["date"])
    
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    for day in days:
        date = datetime.strptime(day["date"], "%Y-%m-%d").date()
        count = day["contributionCount"]
        
        if count > 0:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            # Check if it's today (no contribution yet is OK) or yesterday
            if date < yesterday:
                temp_streak = 0
    
    # Calculate current streak (from today or yesterday backwards)
    days_with_contrib = [d for d in days if d["contributionCount"] > 0]
    if days_with_contrib:
        last_contrib = datetime.strptime(days_with_contrib[-1]["date"], "%Y-%m-%d").date()
        if last_contrib >= yesterday:
            # Count backwards from last contribution
            current_streak = 0
            for day in reversed(days):
                date = datetime.strptime(day["date"], "%Y-%m-%d").date()
                if day["contributionCount"] > 0:
                    current_streak += 1
                elif date < yesterday:
                    break
    
    return {
        "total": calendar["totalContributions"],
        "current": current_streak,
        "longest": longest_streak
    }


def get_repo_head_commit(repo_path):
    """Get HEAD commit hash for caching."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except:
        return None


def clone_repo(repo_name, temp_dir):
    """Clone a repository."""
    repo_path = temp_dir / repo_name.replace("/", "_")
    if repo_path.exists():
        # Pull latest changes
        subprocess.run(
            ["git", "-C", str(repo_path), "pull", "--quiet"],
            capture_output=True
        )
    else:
        # Clone with minimal history for speed
        subprocess.run(
            ["git", "clone", "--depth", "100", 
             f"https://{os.environ['GH_TOKEN']}@github.com/{repo_name}.git",
             str(repo_path)],
            capture_output=True,
            check=True
        )
    return repo_path


def count_lines_with_blame(repo_path, username):
    """
    Count lines written by specific user using parallel git blame.
    Optimized with xargs -P for maximum speed.
    """
    # Get list of files
    result = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files", "-z"],
        capture_output=True, text=True
    )
    files = result.stdout.split('\0')[:-1]  # Remove last empty string
    
    if not files:
        return {}
    
    # Use xargs with parallel processing for git blame
    # This is much faster than sequential Python
    cmd = (
        f'cd {repo_path} && '
        f'git ls-files -z | '
        f'xargs -0rn1 -P "$(nproc)" -I{{}} '
        f'sh -c \'git blame -w -M -C -C --line-porcelain -- "{{}}" 2>/dev/null | grep "^author "\''
    )
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        executable='/bin/bash'
    )
    
    # Parse output and count lines per author
    author_lines = defaultdict(int)
    for line in result.stdout.split('\n'):
        if line.startswith('author '):
            author = line[7:].strip()
            author_lines[author] += 1
    
    # Filter for target username (case insensitive)
    target_lines = {}
    for author, count in author_lines.items():
        if author.lower() == username.lower():
            target_lines[author] = count
    
    return target_lines


def get_file_extensions_breakdown(repo_path, username):
    """Get lines per file extension for a specific user."""
    # Get all files with their extensions
    result = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files"],
        capture_output=True, text=True
    )
    files = result.stdout.strip().split('\n')
    
    ext_lines = defaultdict(int)
    
    for file in files:
        if not file:
            continue
            
        # Get extension
        ext = Path(file).suffix.lower()
        if not ext:
            ext = "(no extension)"
        
        # Run blame on this file only for target user
        # Use --line-porcelain and grep for efficiency
        cmd = (
            f'cd {repo_path} && '
            f'git blame -w -M -C -C --line-porcelain -- "{file}" 2>/dev/null | '
            f'grep "^author " | grep -i "{username}" | wc -l'
        )
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            executable='/bin/bash'
        )
        
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        if count > 0:
            ext_lines[ext] += count
    
    return dict(ext_lines)


def process_repo(repo_name, cache, temp_dir):
    """Process a single repository."""
    print(f"Processing {repo_name}...")
    
    try:
        repo_path = clone_repo(repo_name, temp_dir)
        head_commit = get_repo_head_commit(repo_path)
        
        # Check cache
        if repo_name in cache and cache[repo_name].get("commit") == head_commit:
            print(f"  {repo_name}: Using cached data")
            return repo_name, cache[repo_name]["data"]
        
        # Get lines by extension (more detailed than just total)
        lines_by_ext = get_file_extensions_breakdown(repo_path, USERNAME)
        
        # Map extensions to languages (simplified)
        #ext_to_lang = None
        
        # Aggregate by language
        lang_lines = defaultdict(int)
        for ext, count in lines_by_ext.items():
            lang = ext_to_lang.get(ext, ext.lstrip('.').upper() if ext != "(no extension)" else "Other")
            lang_lines[lang] += count
        
        data = {
            "languages": dict(lang_lines),
            "total": sum(lines_by_ext.values())
        }
        
        # Update cache
        cache[repo_name] = {
            "commit": head_commit,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"  {repo_name}: {data['total']} lines")
        return repo_name, data
        
    except Exception as e:
        print(f"  Error processing {repo_name}: {e}")
        return repo_name, {"languages": {}, "total": 0}


def get_huggingface_stats():
    """Get HuggingFace models and download stats."""
    headers = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"}
    
    # Get models
    models_url = f"{HF_API}/models?author={HF_USERNAME}"
    response = requests.get(models_url, headers=headers)
    models = response.json() if response.status_code == 200 else []
    
    # Get datasets
    datasets_url = f"{HF_API}/datasets?author={HF_USERNAME}"
    response = requests.get(datasets_url, headers=headers)
    datasets = response.json() if response.status_code == 200 else []
    
    total_downloads = sum(m.get("downloads", 0) for m in models)
    total_likes = sum(m.get("likes", 0) for m in models)
    
    return {
        "models": len(models),
        "datasets": len(datasets),
        "downloads": total_downloads,
        "likes": total_likes,
        "model_list": [{"name": m["id"], "downloads": m.get("downloads", 0)} for m in models[:5]]
    }


def generate_lines_svg(lang_stats, top_n=8):
    """Generate SVG for lines of code by language."""
    # Utilise EXCLUDED_LANGS importé depuis ext_to_lang
    filtered_stats = {k: v for k, v in lang_stats.items() if k not in EXCLUDED_LANGS}
    
    # Trier et prendre top N
    sorted_langs = sorted(filtered_stats.items(), key=lambda x: x[1], reverse=True)
    
    # Compléter avec des placeholders si moins de 8
    while len(sorted_langs) < top_n:
        sorted_langs.append(("-", 0))
    
    # Prendre seulement top_n
    sorted_langs = sorted_langs[:top_n]
    
    total = sum(filtered_stats.values())
    if total == 0:
        total = 1
    
    # Dimensions
    width = 600
    row_height = 25
    header_height = 40
    height = header_height + (len(sorted_langs) * row_height) + 20
    
    # Barres réduites
    max_lines = max([v for _, v in sorted_langs]) if sorted_langs else 1
    max_bar_width = 350
    
    bars = []
    y = header_height
    for lang, lines in sorted_langs:
        percentage = (lines / total * 100)
        bar_width = (lines / max_lines * max_bar_width) if max_lines > 0 else 0
        
        color = "#444444" if lang == "-" else "#ffffff"
        
        bars.append(f'''
        <g transform="translate(20, {y})">
            <text x="0" y="15" fill="{color}" font-family="monospace" font-size="12">{lang}</text>
            <rect x="120" y="2" width="{bar_width}" height="18" fill="#ffffff" opacity="0.8"/>
            <text x="{125 + bar_width}" y="15" fill="#aaaaaa" font-family="monospace" font-size="11">{lines:,} ({percentage:.1f}%)</text>
        </g>
        ''')
        y += row_height
    
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="#000000"/>
    <text x="20" y="25" fill="#ffffff" font-family="monospace" font-size="14" font-weight="bold">Lines of Code by Language</text>
    <text x="20" y="{height - 10}" fill="#888888" font-family="monospace" font-size="10">Total: {sum(filtered_stats.values()):,} lines</text>
    {''.join(bars)}
</svg>'''
    
    return svg


def generate_streak_svg(streak_data):
    """Generate SVG for GitHub streak stats."""
    width = 640  # Augmenté
    height = 130  # Un peu plus haut pour la légende
    
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="#000000"/>
    <text x="320" y="20" fill="#ffffff" font-family="monospace" font-size="14" font-weight="bold" text-anchor="middle">GitHub Contributions</text>
    <text x="320" y="35" fill="#666666" font-family="monospace" font-size="10" text-anchor="middle">Last 12 months</text>
    
    <g transform="translate(80, 60)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Total</text>
        <text x="0" y="25" fill="#ffffff" font-family="monospace" font-size="20" font-weight="bold">{streak_data['total']:,}</text>
    </g>
    
    <g transform="translate(280, 60)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Current Streak</text>
        <text x="0" y="25" fill="#ffffff" font-family="monospace" font-size="20" font-weight="bold">{streak_data['current']}</text>
        <text x="0" y="40" fill="#888888" font-family="monospace" font-size="9">days</text>
    </g>
    
    <g transform="translate(480, 60)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Longest Streak</text>
        <text x="0" y="25" fill="#ffffff" font-family="monospace" font-size="20" font-weight="bold">{streak_data['longest']}</text>
        <text x="0" y="40" fill="#888888" font-family="monospace" font-size="9">days</text>
    </g>
</svg>'''
    
    return svg


def generate_hf_svg(hf_stats):
    """Generate SVG for HuggingFace stats."""
    width = 640  # Augmenté
    height = 100 + (len(hf_stats['model_list']) * 20)
    
    model_rows = []
    y = 80
    for model in hf_stats['model_list']:
        model_rows.append(f'''
        <text x="20" y="{y}" fill="#cccccc" font-family="monospace" font-size="10">{model['name'].split('/')[-1][:40]}</text>
        <text x="450" y="{y}" fill="#ffffff" font-family="monospace" font-size="10" text-anchor="end">{model['downloads']:,} downloads</text>
        ''')
        y += 20
    
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="#000000"/>
    <text x="20" y="25" fill="#ffffff" font-family="monospace" font-size="14" font-weight="bold">HuggingFace Hub</text>
    
    <g transform="translate(20, 45)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Models</text>
        <text x="0" y="15" fill="#ffffff" font-family="monospace" font-size="16" font-weight="bold">{hf_stats['models']}</text>
    </g>
    
    <g transform="translate(140, 45)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Datasets</text>
        <text x="0" y="15" fill="#ffffff" font-family="monospace" font-size="16" font-weight="bold">{hf_stats['datasets']}</text>
    </g>
    
    <g transform="translate(260, 45)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Downloads</text>
        <text x="0" y="15" fill="#ffffff" font-family="monospace" font-size="16" font-weight="bold">{hf_stats['downloads']:,}</text>
    </g>
    
    <g transform="translate(420, 45)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Likes</text>
        <text x="0" y="15" fill="#ffffff" font-family="monospace" font-size="16" font-weight="bold">{hf_stats['likes']}</text>
    </g>
    
    <text x="20" y="70" fill="#666666" font-family="monospace" font-size="11">Top Models:</text>
    {''.join(model_rows)}
</svg>'''
    
    return svg


def generate_repo_svg(repo_name, repo_data):
    """Generate SVG for a specific tracked repository."""
    width = 640  # Augmenté
    height = 120
    
    total_lines = repo_data.get('total', 0)
    langs = repo_data.get('languages', {})
    top_lang = max(langs.items(), key=lambda x: x[1]) if langs else ('N/A', 0)
    
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="#000000"/>
    <text x="20" y="25" fill="#ffffff" font-family="monospace" font-size="13" font-weight="bold">{repo_name}</text>
    
    <g transform="translate(20, 50)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Your Lines</text>
        <text x="0" y="20" fill="#ffffff" font-family="monospace" font-size="18" font-weight="bold">{total_lines:,}</text>
    </g>
    
    <g transform="translate(180, 50)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Top Language</text>
        <text x="0" y="20" fill="#ffffff" font-family="monospace" font-size="14" font-weight="bold">{top_lang[0]}</text>
        <text x="0" y="35" fill="#888888" font-family="monospace" font-size="9">{top_lang[1]:,} lines</text>
    </g>
    
    <g transform="translate(400, 50)">
        <text x="0" y="0" fill="#888888" font-family="monospace" font-size="10">Languages</text>
        <text x="0" y="20" fill="#ffffff" font-family="monospace" font-size="18" font-weight="bold">{len(langs)}</text>
    </g>
</svg>'''
    
    return svg


def main():
    """Main function."""
    print("Starting stats generation...")
    
    # Ensure stats directory exists
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load cache
    cache = load_cache()
    
    # Get config
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    
    tracked_repos = [f"{r['owner']}/{r['name']}" for r in config.get('tracked_repos', [])]
    
    # Create temp directory for cloning
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        
        # Get user's own repos
        print("Fetching user repositories...")
        own_repos = get_user_repos()
        all_repos = list(set(own_repos + tracked_repos))
        print(f"Found {len(all_repos)} repositories to process")
        
        # Process repos in parallel
        all_lang_stats = defaultdict(int)
        repo_stats = {}
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(process_repo, repo, cache, temp_dir): repo 
                for repo in all_repos
            }
            
            for future in as_completed(futures):
                repo_name, data = future.result()
                repo_stats[repo_name] = data
                
                # Aggregate language stats for own repos only
                if repo_name in own_repos:
                    for lang, lines in data.get('languages', {}).items():
                        all_lang_stats[lang] += lines
        
        # Save updated cache
        save_cache(cache)
        
        # Get GitHub streak
        print("Fetching GitHub contributions...")
        calendar = get_contribution_calendar()
        streak_data = calculate_streak(calendar)
        
        # Get HuggingFace stats
        print("Fetching HuggingFace stats...")
        hf_stats = get_huggingface_stats()
    
    # Generate SVGs
    print("Generating SVGs...")
    
    # 1. Lines of code by language
    lines_svg = generate_lines_svg(dict(all_lang_stats))
    with open(STATS_DIR / "github-lines.svg", 'w') as f:
        f.write(lines_svg)
    
    # 2. Streak stats
    streak_svg = generate_streak_svg(streak_data)
    with open(STATS_DIR / "github-streak.svg", 'w') as f:
        f.write(streak_svg)
    
    # 3. HuggingFace stats
    hf_svg = generate_hf_svg(hf_stats)
    with open(STATS_DIR / "huggingface-stats.svg", 'w') as f:
        f.write(hf_svg)
    
    # 4. Tracked repos
    for repo_name in tracked_repos:
        if repo_name in repo_stats:
            safe_name = repo_name.replace("/", "-")
            repo_svg = generate_repo_svg(repo_name, repo_stats[repo_name])
            with open(STATS_DIR / f"repo-{safe_name}.svg", 'w') as f:
                f.write(repo_svg)
    
    print(f"Done! Generated {len(list(STATS_DIR.glob('*.svg')))} SVGs")
    print(f"Total lines across all your repos: {sum(all_lang_stats.values()):,}")


if __name__ == "__main__":
    main()