import os
import sys

import yaml

repos = {}
config = {
    "token": os.environ["GITHUB_TOKEN"],
    "repos": repos,
}

repos["nightly.link"] = {
    "queries": [("https://nightly.link", "-path:.github/workflows")],
    "min_stars": 8,
}
repos["nightly.link in workflows"] = {
    "queries": [("https://nightly.link", "path:.github/workflows")],
    "min_stars": 5,
}

for name, min_stars in [
    ("install-crystal", 4),
    ("find-latest-tag", 13),
]:
    queries = [
        (f"oprypin/{name}", "path:.github/workflows language:yaml"),
    ]
    repos[name] = {"queries": queries, "min_stars": min_stars}

for name, plugname, *query, min_stars in [
    ("mkdocstrings-crystal", "mkdocstrings", "default_handler", "crystal", 0),
    ("mkdocs-section-index", "section-index", 2),
    ("mkdocs-literate-nav", "literate-nav", 0),
    ("mkdocs-gen-files", "gen-files", 0),
    ("mkdocs-same-dir", "same-dir", 0),
    ("mkdocstrings", "mkdocstrings", "-crystal", 10),
    ("mkdocs-autorefs", "autorefs", 3),
]:
    query = query or [""]
    query[-1] += " filename:mkdocs.yml"
    queries = [
        ("plugins", "- " + plugname, *query),
        (name, "filename:requirements.txt"),
    ]
    if name in ["mkdocstrings", "mkdocs-autorefs"]:
        del queries[-1]
    repos[name] = {"queries": queries, "min_stars": min_stars}

for name, require, min_stars in [
    ("crsfml", "crsfml", 1),
    ("crystal-chipmunk", "chipmunk", 1),
    ("crystal-imgui", None, 0),
]:
    queries = [(f"oprypin/{name}", "filename:shard.yml")]
    if require:
        queries += [(f'require "{require}"', "language:crystal")]

    repos[name] = {"queries": queries, "min_stars": min_stars}

for name, imprt, min_stars in [
    ("pytest-golden", "pytest_golden", 0),
]:
    queries = [
        (imprt, "language:python"),
        (name, "filename:requirements.txt"),
    ]
    repos[name] = {"queries": queries, "min_stars": min_stars}


yaml.safe_dump(config, sys.stdout, sort_keys=False)
