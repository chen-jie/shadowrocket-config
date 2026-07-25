#!/usr/bin/env python3

import os
from pathlib import Path


CONFIG_FILE = Path("output/shadowrocket.conf")


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