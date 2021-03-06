# Egobooster

Search GitHub for new usages of your projects.

Every time you run this, it will [search GitHub](https://github.com/search?q=foo&type=code) for the queries that you specify. It lets you know about all matching results: when and where each repository started using the project as per the query.

The results from each run are stored under `repos/*.yml`. The following runs will not repeat pre-existing findings. But you can still look at all findings in the YAML files themselves.

You can configure it to not show results unless they have at least N stars, per-repo.

A GitHub token is required. [Generate one](https://github.com/settings/tokens/new) - don't select any permission checkboxes.

## Config format

Example:

```yaml
token: fefefefefefefefefefefefefefefefefefefefe
repos:
  some-repo-alias:
    queries:
    - - search exactly!
      - another exact search
      - mandatory freeform search path:foo language:python
    - - mandatory freeform search goes last
    min_stars: 7
  another-repo-alias:
    queries: ...
    min_stars: ...
```

For the first repo this will use the GitHub token to perform searches with the following two queries:

```
"search exactly!" "another exact search" mandatory freeform search path:foo language:python
```
```
mandatory freeform search goes last
```

Only the last query list item is directly passed through to GitHub search, others are quoted and afterwards additionally double-checked that the file actually contains that text, because GitHub fuzzily disregards non-word characters. For the example above this ensures that the phrase "search exactly" isn't matched unless it is actually followed by an exclamation mark.

Note: Don't rely on the "double-checking" too much and ensure that the query doesn't produce an unreasonable number of results in the first place. Just check how many results GitHub's web interface produces itself. The script conveniently prints out the queries that it performs.

For each repo that matches any of the above queries and has at least 7 stars, it will print new usages: the repository, star count, and the exact file(s).

## Usage

```bash
python3 -m pip install -r requirements.txt
```

```bash
python3 egobooster.py config.yml
```

The config needs to be created in the first place. It is recommended to generate the config from a script, for better reuse. For inspiration, try:

```bash
GITHUB_TOKEN=fefefefefefefefefefefefefefefefefefefefe python3 config/oprypin.py > config/oprypin.yml
```

You can avoid the intermediate file too.

```bash
python3 config/oprypin.py | python3 egobooster.py -
```

## Development

Format code:

```bash
isort . && black -l100 .
```

Run tests:

```bash
PYTHONPATH=. pytest
```
