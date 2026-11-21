# Mihomo 节点池

每 6 小时更新一次公开订阅源。节点通过 Mihomo 的 delay API 测速，成功的节点按延迟排序，写入 `clash-subscription.yaml`。失败节点不进入结果；没有可用节点时保留上次订阅。

本地运行：

```sh
python -m pip install -r requirements.txt
python scripts/aggregate.py
python scripts/benchmark.py --mihomo /path/to/mihomo
/path/to/mihomo -t -d /tmp/mihomo-check -f clash-subscription.yaml
```

`benchmark.json` 记录测试时间、成功数和延迟范围。源文件见 `scripts/aggregate.py`；工作流支持定时和手动运行。
