import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


UPDATE_SCRIPT = Path(__file__).parents[1] / "scripts" / "update.py"
SPEC = importlib.util.spec_from_file_location("update", UPDATE_SCRIPT)
update = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update)


class CustomRulesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.rules_dir = Path(self.temp_dir.name)

    def write_rule_file(self, name, content):
        rule_file = self.rules_dir / name
        rule_file.write_text(content, encoding="utf-8")
        return rule_file

    def test_inject_custom_rules_precedes_upstream_rules(self):
        rule_files = {
            "DIRECT": self.write_rule_file(
                "direct.list", "# LAN devices\nDOMAIN-SUFFIX,lan.example\n"
            ),
            "PROXY": self.write_rule_file(
                "proxy.list", "# Remote service\nDOMAIN-SUFFIX,proxy.example\n"
            ),
            "REJECT": self.write_rule_file(
                "reject.list", "DOMAIN-SUFFIX,ads.example\n"
            ),
        }

        result = update.inject_custom_rules(
            "[Rule]\nDOMAIN-SUFFIX,upstream.example,Proxy\nFINAL,direct\n",
            rule_files,
        )

        self.assertIn("# Local custom DIRECT rules", result)
        self.assertIn("# LAN devices", result)
        self.assertIn("DOMAIN-SUFFIX,lan.example,DIRECT", result)
        self.assertIn("DOMAIN-SUFFIX,proxy.example,PROXY", result)
        self.assertIn("DOMAIN-SUFFIX,ads.example,REJECT", result)
        self.assertLess(result.index("[Rule]"), result.index("# BEGIN LOCAL CUSTOM RULES"))
        self.assertLess(
            result.index("# BEGIN LOCAL CUSTOM RULES"),
            result.index("DOMAIN-SUFFIX,upstream.example,Proxy"),
        )

    def test_inject_custom_rules_replaces_existing_generated_block(self):
        rule_files = {
            "DIRECT": self.write_rule_file("direct.list", "DOMAIN,local.example\n")
        }
        source = "[Rule]\nFINAL,direct\n"

        once = update.inject_custom_rules(source, rule_files)
        twice = update.inject_custom_rules(once, rule_files)

        self.assertEqual(twice, once)
        self.assertEqual(twice.count("# BEGIN LOCAL CUSTOM RULES"), 1)

    def test_inject_custom_rules_requires_rule_section_and_final(self):
        rule_files = {
            "DIRECT": self.write_rule_file("direct.list", "DOMAIN,local.example\n")
        }

        with self.assertRaisesRegex(ValueError, r"\[Rule\]"):
            update.inject_custom_rules("[General]\n", rule_files)
        with self.assertRaisesRegex(ValueError, "FINAL,direct"):
            update.inject_custom_rules("[Rule]\n", rule_files)

    def test_main_writes_dns_and_local_rules(self):
        config_file = self.rules_dir / "shadowrocket.conf"
        config_file.write_text("[General]\n[Rule]\nFINAL,direct\n", encoding="utf-8")
        original_config_file = update.CONFIG_FILE
        original_rule_files = getattr(update, "RULE_FILES", None)
        original_profile = os.environ.get("NEXTDNS_PROFILE")
        self.addCleanup(setattr, update, "CONFIG_FILE", original_config_file)

        update.CONFIG_FILE = config_file
        update.RULE_FILES = {
            "DIRECT": self.write_rule_file("direct.list", "DOMAIN,local.example\n")
        }
        os.environ["NEXTDNS_PROFILE"] = "test-profile"

        def restore_environment():
            if original_profile is None:
                os.environ.pop("NEXTDNS_PROFILE", None)
            else:
                os.environ["NEXTDNS_PROFILE"] = original_profile

            if original_rule_files is None:
                delattr(update, "RULE_FILES")
            else:
                update.RULE_FILES = original_rule_files

        self.addCleanup(restore_environment)

        update.main()

        result = config_file.read_text(encoding="utf-8")
        self.assertIn("dns-server = test-profile", result)
        self.assertIn("DOMAIN,local.example,DIRECT", result)
