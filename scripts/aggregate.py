#!/usr/bin/env python3
"""Aggregate public Mihomo-compatible proxy feeds into a proxy-provider file."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_NODES = ROOT / "nodes.yaml"
OUT_REPORT = ROOT / "report.json"
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = 25
USER_AGENT = "mihomo-pool-crawler/1.0 (+https://github.com/)"
SUPPORTED_TYPES = {
    "ss", "ssr", "vmess", "vless", "trojan", "socks5", "http", "socks4",
    "snell", "wireguard", "hysteria", "hysteria2", "tuic", "ssh", "anytls",
}
SOURCES = {
    "freeSub": "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml",
    "NoMoreWalls": "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.meta.yml",
    "AutoMergePublicNodes": "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.meta.yml",
    "zhuhaiuk": "https://raw.githubusercontent.com/zhuhaiuk/free-nodes/main/clash_config.yaml",
    "free18": "https://raw.githubusercontent.com/free18/v2ray/main/c.yaml",
    "ermaozi": "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
    "Eternity": "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml",
    "anaer-Sub": "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
    "yy1588133-proxy-pool": "https://raw.githubusercontent.com/yy1588133/proxy-pool/main/clash.yaml",
    "go4sharing-sub": "https://raw.githubusercontent.com/go4sharing/sub/main/clash.yaml",
    "wzmwayne-proxy-node": "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/aio/clash.yaml",
    "735754647-Free-Nodes": "https://735754647.github.io/Free-Nodes/clash.yaml",
    "steam-100-free-proxy-sub": "https://raw.githubusercontent.com/steam-100/free-proxy-sub/data/clash.yaml",
    "ermao-blog": "https://blog.ermao.net/sub/clash/ermao.net",
    "PuddinCat-BestClash": "https://raw.githubusercontent.com/PuddinCat/BestClash/refs/heads/main/proxies.yaml",
    "snakem982-proxypool": "https://raw.githubusercontent.com/snakem982/proxypool/main/source/clash-meta-2.yaml",
    "OgdenThomas-freesub": "https://cdn.jsdelivr.net/gh/OgdenThomas/freesub@main/output/clash.yaml",
}


def fetch(url: str) -> tuple[str | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return None, "feed exceeds 8 MiB limit"
        return body.decode("utf-8-sig", errors="replace"), None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, type(exc).__name__


def parse_document(text: str) -> list[dict[str, Any]]:
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if isinstance(document, dict):
        candidates = document.get("proxies", [])
    elif isinstance(document, list):
        candidates = document
    else:
        candidates = []
    return [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []


def is_valid_proxy(proxy: dict[str, Any]) -> bool:
    kind = str(proxy.get("type", "")).lower()
    server = proxy.get("server")
    port = proxy.get("port")
    if kind not in SUPPORTED_TYPES or not isinstance(server, str) or not server.strip():
        return False
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return False
    host = server.strip().lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain", "0.0.0.0", "::", "::1"}:
        return False
    if re.fullmatch(r"127(?:\.\d{1,3}){3}", host) or host.endswith(".localhost"):
        return False
    return True


def canonical(proxy: dict[str, Any]) -> str:
    normalized = {key: value for key, value in proxy.items() if key != "name"}
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def aggregate(source_urls: dict[str, str], workers: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fetched: dict[str, tuple[str | None, str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {executor.submit(fetch, url): name for name, url in source_urls.items()}
        for job in concurrent.futures.as_completed(jobs):
            fetched[jobs[job]] = job.result()

    unique: dict[str, dict[str, Any]] = {}
    source_stats: dict[str, dict[str, Any]] = {}
    for name, url in source_urls.items():
        text, error = fetched[name]
        if text is None:
            source_stats[name] = {"url": url, "ok": False, "error": error, "nodes": 0}
            print(f"[skip] {name}: {error}", file=sys.stderr)
            continue
        parsed = parse_document(text)
        accepted = 0
        for proxy in parsed:
            if not is_valid_proxy(proxy):
                continue
            key = canonical(proxy)
            if key not in unique:
                clean = dict(proxy)
                clean["name"] = str(clean.get("name") or f"{clean['type']}-{clean['server']}:{clean['port']}")[:128]
                unique[key] = clean
                accepted += 1
        source_stats[name] = {"url": url, "ok": True, "nodes": accepted, "parsed": len(parsed)}
        print(f"[ok] {name}: {accepted} unique, {len(parsed)} parsed")

    nodes = list(unique.values())
    nodes.sort(key=lambda item: (str(item.get("name", "")).casefold(), str(item.get("server", "")), int(item.get("port", 0))))
    report = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_nodes": len(nodes),
        "sources": source_stats,
    }
    return nodes, report


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(source_urls: dict[str, str], nodes_path: Path, report_path: Path) -> int:
    nodes, report = aggregate(source_urls)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not nodes:
        print("No valid nodes found; preserving existing output.", file=sys.stderr)
        return 1
    nodes_text = yaml.safe_dump({"proxies": nodes}, allow_unicode=True, sort_keys=False, width=120)
    atomic_write(nodes_path, nodes_text)
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {len(nodes)} nodes to {nodes_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=Path, default=OUT_NODES)
    parser.add_argument("--report", type=Path, default=OUT_REPORT)
    parser.add_argument("--source", action="append", default=[], metavar="NAME=URL", help="replace defaults with explicit sources; repeatable")
    args = parser.parse_args()
    sources = SOURCES
    if args.source:
        sources = {}
        for item in args.source:
            if "=" not in item:
                parser.error(f"invalid --source {item!r}; expected NAME=URL")
            name, url = item.split("=", 1)
            if not name or not url.startswith("https://"):
                parser.error("source names must be nonempty and URLs must use https")
            sources[name] = url
    return run(sources, args.nodes.resolve(), args.report.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
