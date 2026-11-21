# Mihomo Pool Crawler

Standalone GitHub Actions crawler that aggregates public Mihomo/Clash YAML feeds into `nodes.yaml`.
It does not read or edit the local Mihomo configuration.

## Run locally

```bash
python -m pip install -r requirements.txt
python scripts/aggregate.py
```

Use explicit HTTPS feeds instead of the bundled list:

```bash
python scripts/aggregate.py \
  --source example=https://example.org/proxies.yaml
```

The output is a Mihomo proxy-provider payload (`proxies:`). `report.json` records per-feed
fetch and parse counts. A run that finds no valid nodes exits nonzero and preserves the prior
output. HTTP requests have bounded time/size, feeds are parsed with `yaml.safe_load`, loopback
placeholders are rejected, and duplicate node configurations are removed.

## GitHub Actions

The workflow runs every six hours (UTC) and supports manual dispatch. Enable Actions and grant
the repository's workflow token permission to write repository contents if automatic commits
are desired. You can consume `nodes.yaml` as a Mihomo `proxy-providers` file after publishing
this repository; keep it private if you do not want to redistribute the upstream node entries.

## Bundled public feeds

- [Ruk1ng001/freeSub](https://github.com/Ruk1ng001/freeSub)
- [peasoft/NoMoreWalls](https://github.com/peasoft/NoMoreWalls)
- [chengaopan/AutoMergePublicNodes](https://github.com/chengaopan/AutoMergePublicNodes)
- [zhuhaiuk/free-nodes](https://github.com/zhuhaiuk/free-nodes)
- [free18/v2ray](https://github.com/free18/v2ray)
- [ermaozi/get_subscribe](https://github.com/ermaozi/get_subscribe)
- [mahdibland/ShadowsocksAggregator](https://github.com/mahdibland/ShadowsocksAggregator)

Public feeds are volatile and not vetted by this project. Verify source trust before routing
sensitive traffic through a node. Respect source repository licenses and service terms.
