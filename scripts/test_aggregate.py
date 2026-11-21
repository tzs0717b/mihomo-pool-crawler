import unittest

from aggregate import canonical, is_valid_proxy, parse_document


class AggregateTests(unittest.TestCase):
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
