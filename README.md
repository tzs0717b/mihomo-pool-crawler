# Mihomo 节点池

订阅地址：

```text
https://raw.githubusercontent.com/tzs0717b/mihomo-pool-crawler/main/clash-subscription.yaml
```

默认自动选择低延迟节点，每 5 分钟重新检测；局域网和国内流量直连，其余走「节点选择」。也可以手动指定节点。

标题格式：`🇯🇵 日本 · 598ms · 0.3MB/s`。国旗和地区沿用上游标记，没有标记的显示「🌐 未知地区」，未经出口 IP 核实。延迟用 HTTPS 204 探测；带宽只对延迟最低的 10 个节点做 256 KiB 下载抽样，结果是近似值，不代表持续带宽。未测或失败的节点标题不标速度。客户端后续自动测速不会改写标题。

目前手动更新，未启用 Actions。配置适用于 Mihomo/Clash Meta。

本地运行：

```sh
python -m pip install -r requirements.txt
python scripts/aggregate.py
python scripts/benchmark.py --mihomo /path/to/mihomo
/path/to/mihomo -t -d /tmp/mihomo-check -f clash-subscription.yaml
```

`benchmark.json` 记录测试时间、成功数和延迟范围。

## 采集源

- [Ruk1ng001/freeSub](https://github.com/Ruk1ng001/freeSub)
- [peasoft/NoMoreWalls](https://github.com/peasoft/NoMoreWalls)
- [chengaopan/AutoMergePublicNodes](https://github.com/chengaopan/AutoMergePublicNodes)
- [zhuhaiuk/free-nodes](https://github.com/zhuhaiuk/free-nodes)
- [free18/v2ray](https://github.com/free18/v2ray)
- [ermaozi/get_subscribe](https://github.com/ermaozi/get_subscribe)
- [mahdibland/ShadowsocksAggregator](https://github.com/mahdibland/ShadowsocksAggregator)
- [anaer/Sub](https://github.com/anaer/Sub)
- [yy1588133/proxy-pool](https://github.com/yy1588133/proxy-pool)
- [go4sharing/sub](https://github.com/go4sharing/sub)
- [wzmwayne/proxy-node](https://github.com/wzmwayne/proxy-node)
- [735754647/Free-Nodes](https://github.com/735754647/Free-Nodes)
- [steam-100/free-proxy-sub](https://github.com/steam-100/free-proxy-sub)

`report.json` 记录每个源的抓取数量和去重后的新增数量。上游大多也是聚合池；地址能抓取不代表节点可用，可用性以本机测速为准。
