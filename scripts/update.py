#!/usr/bin/env python3

import os
from pathlib import Path


CONFIG_FILE = Path("output/shadowrocket.conf")
RULE_FILES = {
    "DIRECT": Path("rules/direct.list"),
    "PROXY": Path("rules/proxy.list"),
    "REJECT": Path("rules/reject.list"),
}
CUSTOM_RULES_START = "# BEGIN LOCAL CUSTOM RULES"
CUSTOM_RULES_END = "# END LOCAL CUSTOM RULES"


def build_custom_rules_block(rule_files: dict[str, Path]) -> str:
    lines = [CUSTOM_RULES_START]

    for policy, rule_file in rule_files.items():
        if not rule_file.exists():
            raise FileNotFoundError(rule_file)

        lines.append(f"# Local custom {policy} rules")

        for line in rule_file.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#"):
                lines.append(line)
            else:
                lines.append(f"{line},{policy}")

    lines.append(CUSTOM_RULES_END)
    return "\n".join(lines)


def remove_custom_rules_block(text: str) -> str:
    while CUSTOM_RULES_START in text:
        start = text.index(CUSTOM_RULES_START)
        end = text.index(CUSTOM_RULES_END, start) + len(CUSTOM_RULES_END)

        if end < len(text) and text[end] == "\n":
            end += 1

        text = text[:start] + text[end:]

    return text


def inject_custom_rules(text: str, rule_files: dict[str, Path]) -> str:
    if "[Rule]" not in text:
        raise ValueError("Configuration does not contain a [Rule] section.")

    if "FINAL,direct" not in text:
        raise ValueError("Configuration does not contain FINAL,direct.")

    text = remove_custom_rules_block(text)
    block = build_custom_rules_block(rule_files)
    return text.replace("FINAL,direct", f"{block}\nFINAL,direct", 1)


def get_nextdns_url() -> str:
    """
    从 GitHub Secret 获取 NextDNS Profile ID
    """

    profile = os.getenv("NEXTDNS_PROFILE")

    if not profile:
        raise RuntimeError(
            "GitHub Secret 'NEXTDNS_PROFILE' 未配置。"
        )

    return f"{profile}"


def replace_dns_server(text: str, nextdns: str) -> str:
    """
    替换 dns-server
    如果不存在，则插入到 [General] 段
    """

    lines = text.splitlines()

    found_general = False
    replaced = False

    result = []

    for line in lines:

        stripped = line.strip()

        if stripped == "[General]":
            found_general = True
            result.append(line)
            continue

        if found_general and stripped.startswith("dns-server ="):
            result.append(f"dns-server = {nextdns}")
            replaced = True
            continue

        result.append(line)

    # 配置里面没有 dns-server
    if not replaced:

        result = []

        inserted = False

        for line in lines:

            result.append(line)

            if line.strip() == "[General]" and not inserted:
                result.append(f"dns-server = {nextdns}")
                inserted = True

    return "\n".join(result) + "\n"


def main():

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(CONFIG_FILE)

    nextdns = get_nextdns_url()

    original = CONFIG_FILE.read_text(encoding="utf-8")

    updated = replace_dns_server(
        original,
        nextdns,
    )
    updated = inject_custom_rules(updated, RULE_FILES)

    if original == updated:
        print("配置无需修改。")
        return

    CONFIG_FILE.write_text(
        updated,
        encoding="utf-8",
    )

    print("NextDNS 已更新。")


if __name__ == "__main__":
    main()
