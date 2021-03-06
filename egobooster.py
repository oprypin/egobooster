#!/usr/bin/env python3

import argparse
import collections
import functools
import json
import os
import random
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

import github
import yaml
from atomicwrites import atomic_write
from tqdm import tqdm


def binary_search(begin, end, lt):
    while begin < end:
        mid = (begin + end) // 2
        if lt(mid):
            begin = mid + 1
        else:
            end = mid
    return begin


def main(all_config):
    # github.enable_console_debug_logging()
    gh = github.Github(all_config["token"], per_page=100)

    Path("repos").mkdir(exist_ok=True)

    aliases_progress = tqdm(all_config["repos"].items(), leave=False)
    for name, config in aliases_progress:
        aliases_progress.set_description(name)

        path = Path("repos", f"{name}.yml")
        try:
            with path.open(encoding="utf-8") as f:
                repos = {repo_info["repo"]: repo_info for repo_info in yaml.safe_load(f)}
        except FileNotFoundError:
            repos = {}

        old_repos = {
            repo_name
            for repo_name, repo_info in repos.items()
            if repo_info.get("stars", 0) >= config.get("min_stars", 0)
        }
        found_repos = {}

        for query in config["queries"]:
            *query_exact, query = query
            query = " ".join(
                filter(None, [w.replace('"', " ").join('""') for w in query_exact] + [query])
            )

            results = gh.search_code(query)
            for result in tqdm(results, total=results.totalCount, desc=query, leave=False):
                repo_name = result.repository.full_name
                try:
                    repo_info = repos[repo_name]
                except KeyError:
                    if not all(w.encode() in result.decoded_content for w in query_exact):
                        continue
                    repo_info = {
                        "repo": result.repository.full_name,
                        "usages": [],
                    }
                found_repos[repo_name] = repo_info

                new_usage = re.search(
                    r"^https://([^/]+/){3}blob/(?P<sha>[0-9a-f]{40})/(?P<path>.+)", result.html_url
                ).groupdict()
                new_usage["path"] = urllib.parse.unquote(new_usage["path"])
                if new_usage not in repo_info["usages"]:
                    repo_info["usages"].append(new_usage)

        for repo_info in tqdm(found_repos.values(), desc="Content", leave=False):
            repository = None
            if "first_used" not in repo_info and repo_info["usages"]:
                repository = gh.get_repo(repo_info["repo"])

                def yield_usages():
                    for usage in repo_info["usages"]:
                        commits = list(repository.get_commits(**usage))[::-1]

                        @functools.cache
                        def has_content(ref):
                            try:
                                content = repository.get_contents(path=usage["path"], ref=ref)
                            except github.UnknownObjectException:
                                return False
                            return all(w.encode() in content.decoded_content for w in query_exact)

                        index = binary_search(
                            0, len(commits) - 1, lambda i: not has_content(commits[i].sha)
                        )
                        yield commits[index].commit.committer.date

                repo_info["first_used"] = str(min(yield_usages()))

            if repository or "stars" not in repo_info or random.randrange(10) == 0:
                repository = repository or gh.get_repo(repo_info["repo"])
                repo_info["stars"] = repository.stargazers_count

        del_repos = old_repos - found_repos.keys()
        if del_repos:
            print()
            print(f"Dropped usages of {name}:")
            for repo_name in del_repos:
                print(f"* {repo_name}")

        with atomic_write(path, encoding="utf-8", overwrite=True) as f:
            yaml.dump(list(found_repos.values()), f, sort_keys=False)

        added_repos = [
            repo_info
            for repo_name, repo_info in found_repos.items()
            if repo_name not in old_repos and repo_info["stars"] >= config.get("min_stars", 0)
        ]
        added_repos.sort(key=lambda repo_info: repo_info["stars"], reverse=True)
        if added_repos:
            print()
            print(f"New usages of {name}:")
            for repo_info in added_repos:
                repo_url = f"https://github.com/{repo_info['repo']}"
                print(f"  * {repo_url} [{repo_info['stars']} stars]")
                for usage in repo_info["usages"]:
                    print("    * {repo_url}/blob/{sha}/{path}".format(repo_url=repo_url, **usage))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=argparse.FileType("r"))
    args = parser.parse_args()

    main(yaml.safe_load(args.config_file))
