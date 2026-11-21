import unittest

from aggregate import canonical, is_valid_proxy, parse_document
from benchmark import country_info, display_name, config_for_output


class AggregateTests(unittest.TestCase):
    def test_country_flags_and_display_name(self):
        self.assertEqual(country_info("🇯🇵 Japan"), ("🇯🇵", "日本"))
        self.assertEqual(country_info("HK - zhuhai.uk"), ("🇭🇰", "香港"))
        self.assertEqual(display_name("🇩🇪 Germany", 410, 2.35), "🇩🇪 德国 · 410ms · 2.4MB/s")
        self.assertIn("🌐 未知地区", display_name("no region", 800))

    def test_output_group_contains_named_nodes(self):
        config = config_for_output([({"name": "JP node", "type": "ss", "server": "example.org", "port": 443}, 250)], {"JP node": 1.5})
        self.assertEqual(config["proxies"][0]["name"], "🇯🇵 日本 · 250ms · 1.5MB/s")
        self.assertEqual(config["proxy-groups"][0]["type"], "url-test")
        self.assertEqual(config["rules"][-1], "MATCH,节点选择")

    def test_parses_proxy_list(self):
        result = parse_document("proxies:\n  - {name: test, type: socks5, server: 1.2.3.4, port: 1080}\n")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["server"], "1.2.3.4")

    def test_rejects_loopback_and_bad_ports(self):
        template = {"name": "x", "type": "ss", "server": "127.0.0.53", "port": 443}
        self.assertFalse(is_valid_proxy(template))
        template.update(server="example.org", port=70000)
        self.assertFalse(is_valid_proxy(template))

    def test_accepts_supported_proxy(self):
        self.assertTrue(is_valid_proxy({"name": "x", "type": "vless", "server": "node.example", "port": 443}))

    def test_dedupe_ignores_name(self):
        first = {"name": "first", "type": "ss", "server": "node.example", "port": 443}
        second = {**first, "name": "second"}
        self.assertEqual(canonical(first), canonical(second))


if __name__ == "__main__":
    unittest.main()
