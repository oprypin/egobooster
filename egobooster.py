#!/usr/bin/env python3

import argparse
import base64
import collections
import functools
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import httpx
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


class GitHubClient(httpx.Client):
    def __init__(self, token, *args, **kwargs):
        kwargs.setdefault("timeout", 100)
        kwargs.setdefault("base_url", "https://api.github.com/")
        kwargs.setdefault("headers", {}).setdefault("Authorization", f"token {token}")
        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs):
        for _ in range(3):
            resp = super().send(*args, **kwargs)
            if resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
                seconds = int(resp.headers["x-ratelimit-reset"]) - time.time()
                seconds = max(seconds + 1, 1)
                print(f"\nHit a rate limit, will sleep for {seconds:.0f}s.", file=sys.stderr)
                time.sleep(seconds)
                continue
            break
        resp.raise_for_status()
        return GitHubResponse(response=resp, client=self)

    def search_code(self, q, **params):
        return self.get("search/code", params={"q": q, **params})

    def get_repo(self, repo):
        return self.get(f"repos/{repo}")

    def get_commits(self, repo, **params):
        return self.get(f"repos/{repo}/commits", params=params)

    def get_content(self, repo, path, **params):
        resp = self.get(f"repos/{repo}/contents/{urllib.parse.quote(path)}", params=params)

        assert resp["encoding"] == "base64"
        del resp._json["encoding"]
        resp._json["content"] = base64.b64decode(resp["content"])

        return resp


class GitHubResponse:
    def __init__(self, response, client):
        self._json = response.json()
        self.response = response
        self.client = client

    def __getattr__(self, name):
        return getattr(self.response, name)

    def __getitem__(self, key):
        return self._json[key]

    def _pages(self):
        yield self
        resp = self.response
        while "next" in resp.links:
            resp = self.client.get(resp.links["next"]["url"])
            yield resp

    def __iter__(self):
        for page in self._pages():
            page = page._json
            if isinstance(page, dict) and "items" in page:
                page = page["items"]
            yield from page


def main(all_config):
    gh = GitHubClient(token=all_config["token"])

    Path("repos").mkdir(exist_ok=True)

    aliases_progress = tqdm(all_config["repos"].items())
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

            results = gh.search_code(query, per_page=100)
            for result in tqdm(results, total=results["total_count"], desc=query, leave=False):
                repo_name = result["repository"]["full_name"]
                new_usage = re.search(
                    r"^https://([^/]+/){3}blob/(?P<sha>[0-9a-f]{40})/(?P<path>.+)",
                    result["html_url"],
                ).groupdict()
                new_usage["path"] = urllib.parse.unquote(new_usage["path"])

                try:
                    repo_info = repos[repo_name]
                except KeyError:
                    content = gh.get_content(repo_name, new_usage["path"], ref=new_usage["sha"])
                    if not all(w.encode() in content["content"] for w in query_exact):
                        continue
                    repo_info = {"repo": repo_name, "usages": []}
                found_repos[repo_name] = repo_info

                if new_usage not in repo_info["usages"]:
                    repo_info["usages"].append(new_usage)

        for repo_info in tqdm(found_repos.values(), desc="Content", leave=False):
            if "first_used" not in repo_info and repo_info["usages"]:

                def yield_usages():
                    for usage in repo_info["usages"]:
                        commits = list(gh.get_commits(repo_info["repo"], **usage))[::-1]

                        @functools.cache
                        def has_content(ref):
                            try:
                                content = gh.get_content(repo_info["repo"], usage["path"], ref=ref)
                            except httpx.HTTPStatusError:
                                return False
                            return all(w.encode() in content["content"] for w in query_exact)

                        index = binary_search(
                            0, len(commits) - 1, lambda i: not has_content(commits[i]["sha"])
                        )
                        yield commits[index]["commit"]["committer"]["date"]

                repo_info["first_used"] = str(min(yield_usages()))

            if "stars" not in repo_info or random.randrange(10) == 0:
                repository = gh.get_repo(repo_info["repo"])
                repo_info["stars"] = repository["stargazers_count"]

        del_repos = old_repos - found_repos.keys()
        if del_repos:
            print(f"\nDropped usages of {name}:")
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
            print(f"\nNew usages of {name}:")
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
