#!/usr/bin/env python3
"""Probe proxy nodes through Mihomo's local delay API and build a ready-to-use config."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "nodes.yaml"
DEFAULT_OUTPUT = ROOT / "clash-subscription.yaml"
DEFAULT_REPORT = ROOT / "benchmark.json"
TEST_URL = "https://www.gstatic.com/generate_204"


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def load_nodes(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("proxies", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("input must contain a proxies list")
    return [dict(item) for item in raw if isinstance(item, dict) and item.get("name")]


def with_unique_names(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for index, source in enumerate(nodes):
        node = dict(source)
        base = str(node.get("name") or f"node-{index + 1}")[:100]
        name = base
        suffix = 2
        while name in seen:
            name = f"{base[:88]} #{suffix}"
            suffix += 1
        seen.add(name)
        node["name"] = name
        result.append(node)
    return result


def mihomo_config(nodes: list[dict[str, Any]], controller_port: int) -> dict[str, Any]:
    return {
        "allow-lan": False,
        "mode": "rule",
        "log-level": "error",
        "external-controller": f"127.0.0.1:{controller_port}",
        "proxies": nodes,
        "rules": ["MATCH,DIRECT"],
    }


def wait_api(base_url: str, process: subprocess.Popen[str], log_path: Path) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        if process.poll() is not None:
            details = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"Mihomo stopped during startup:\n{details}")
        try:
            with opener.open(f"{base_url}/version", timeout=1.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    details = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
    raise RuntimeError(f"Mihomo API did not start:\n{details}")


def probe(base_url: str, name: str, timeout_ms: int) -> tuple[str, int | None]:
    encoded_name = urllib.parse.quote(name, safe="")
    query = urllib.parse.urlencode({"url": TEST_URL, "timeout": str(timeout_ms)})
    request = urllib.request.Request(f"{base_url}/proxies/{encoded_name}/delay?{query}")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=(timeout_ms / 1000) + 4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        delay = payload.get("delay")
        if isinstance(delay, int) and 0 < delay <= timeout_ms:
            return name, delay
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        pass
    return name, None


COUNTRY_NAMES = {
    "🇨🇳": "中国", "🇭🇰": "香港", "🇲🇴": "澳门", "🇹🇼": "台湾", "🇯🇵": "日本",
    "🇰🇷": "韩国", "🇸🇬": "新加坡", "🇺🇸": "美国", "🇨🇦": "加拿大", "🇬🇧": "英国",
    "🇩🇪": "德国", "🇫🇷": "法国", "🇳🇱": "荷兰", "🇷🇺": "俄罗斯", "🇮🇳": "印度",
    "🇦🇺": "澳大利亚", "🇹🇭": "泰国", "🇻🇳": "越南", "🇲🇾": "马来西亚", "🇮🇩": "印度尼西亚",
    "🇹🇷": "土耳其", "🇮🇹": "意大利", "🇪🇸": "西班牙", "🇵🇱": "波兰", "🇨🇭": "瑞士",
    "🇸🇪": "瑞典", "🇳🇴": "挪威", "🇫🇮": "芬兰", "🇧🇪": "比利时", "🇦🇹": "奥地利",
    "🇧🇷": "巴西", "🇦🇪": "阿联酋", "🇮🇱": "以色列", "🇿🇦": "南非", "🇵🇭": "菲律宾",
}
CODE_NAMES = {
    "CN": "中国", "HK": "香港", "MO": "澳门", "TW": "台湾", "JP": "日本", "KR": "韩国",
    "SG": "新加坡", "US": "美国", "CA": "加拿大", "GB": "英国", "UK": "英国", "DE": "德国",
    "FR": "法国", "NL": "荷兰", "RU": "俄罗斯", "IN": "印度", "AU": "澳大利亚", "TH": "泰国",
    "VN": "越南", "MY": "马来西亚", "ID": "印度尼西亚", "TR": "土耳其", "IT": "意大利",
    "ES": "西班牙", "PL": "波兰", "CH": "瑞士", "SE": "瑞典", "NO": "挪威", "FI": "芬兰",
    "BE": "比利时", "AT": "奥地利", "BR": "巴西", "AE": "阿联酋", "IL": "以色列",
    "ZA": "南非", "PH": "菲律宾",
}


def country_label(name: str) -> str:
    for flag, country in COUNTRY_NAMES.items():
        if flag in name:
            return country
    for code, country in CODE_NAMES.items():
        if re.search(rf"(?<![A-Za-z]){code}(?![A-Za-z])", name.upper()):
            return country
    for country in CODE_NAMES.values():
        if country in name:
            return country
    return "未知地区"


def display_name(source_name: str, delay: int) -> str:
    return f"{country_label(source_name)} · {delay}ms"


def config_for_output(nodes_with_latency: list[tuple[dict[str, Any], int]]) -> dict[str, Any]:
    proxies = []
    used_names: set[str] = set()
    for source, delay in nodes_with_latency:
        node = dict(source)
        base = display_name(str(node.get("name", "")), delay)
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base} #{suffix}"
            suffix += 1
        used_names.add(name)
        node["name"] = name
        proxies.append(node)
    names = [node["name"] for node in proxies]
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "ipv6": False,
        "proxies": proxies,
        "proxy-groups": [
            {"name": "自动测速", "type": "url-test", "proxies": names, "url": TEST_URL, "interval": 300, "tolerance": 80},
            {"name": "节点选择", "type": "select", "proxies": ["自动测速", "DIRECT", *names]},
        ],
        "rules": [
            "GEOSITE,private,DIRECT",
            "GEOSITE,cn,DIRECT",
            "GEOIP,LAN,DIRECT,no-resolve",
            "GEOIP,CN,DIRECT,no-resolve",
            "MATCH,节点选择",
        ],
    }


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(input_path: Path, output_path: Path, report_path: Path, mihomo: str, workers: int, timeout_ms: int) -> int:
    nodes = with_unique_names(load_nodes(input_path))
    if not nodes:
        raise ValueError("no proxy nodes found")

    controller_port = available_port()
    base_url = f"http://127.0.0.1:{controller_port}"
    with tempfile.TemporaryDirectory(prefix="mihomo-benchmark-") as temporary:
        tempdir = Path(temporary)
        config_path = tempdir / "bench.yaml"
        data_dir = tempdir / "data"
        log_path = tempdir / "mihomo.log"
        config_path.write_text(
            yaml.safe_dump(mihomo_config(nodes, controller_port), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        command = [mihomo, "-d", str(data_dir), "-f", str(config_path)]
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            wait_api(base_url, process, log_path)
            success: list[tuple[dict[str, Any], int]] = []
            failures = 0
            lock = threading.Lock()
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(probe, base_url, node["name"], timeout_ms): node for node in nodes}
                for future in concurrent.futures.as_completed(futures):
                    name, delay = future.result()
                    node = futures[future]
                    if delay is None:
                        failures += 1
                    else:
                        success.append((node, delay))
                    with lock:
                        done = len(success) + failures
                        if done % 100 == 0 or done == len(nodes):
                            print(f"probed {done}/{len(nodes)}; alive {len(success)}", flush=True)
            success.sort(key=lambda row: (row[1], row[0]["name"].casefold()))
            if not success:
                print("No nodes passed the latency test; previous output kept.", file=sys.stderr)
                return 1
            config = config_for_output(success)
            content = yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=120)
            atomic_write(output_path, content)
            delays = [delay for _, delay in success]
            report = {
                "tested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "test_url": TEST_URL,
                "tested": len(nodes),
                "alive": len(success),
                "failed": failures,
                "timeout_ms": timeout_ms,
                "latency_ms": {
                    "min": min(delays),
                    "median": sorted(delays)[len(delays) // 2],
                    "max": max(delays),
                },
            }
            atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(f"Wrote {len(success)} tested nodes to {output_path}")
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--mihomo", default=os.environ.get("MIHOMO_BIN", "mihomo"))
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--timeout-ms", type=int, default=4500)
    args = parser.parse_args()
    if not 1 <= args.workers <= 128:
        parser.error("--workers must be between 1 and 128")
    if not 500 <= args.timeout_ms <= 30000:
        parser.error("--timeout-ms must be between 500 and 30000")
    try:
        return run(args.input.resolve(), args.output.resolve(), args.report.resolve(), args.mihomo, args.workers, args.timeout_ms)
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
