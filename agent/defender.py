import argparse
import platform
import subprocess
import threading
import time

from loguru import logger


import re

_IPV4_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_IPV6_PATTERN = re.compile(r"^[0-9a-fA-F:]+$")


def _is_valid_ip(ip: str) -> bool:
    if _IPV4_PATTERN.match(ip):
        return all(0 <= int(o) <= 255 for o in ip.split("."))
    if _IPV6_PATTERN.match(ip):
        return 2 <= len(ip) <= 45
    return False


class IPBlocker:
    def __init__(self) -> None:
        self._platform = platform.system().lower()

    def _rule_name(self, ip: str) -> str:
        return f"AI_IDS_BLOCK_{ip.replace('.', '_').replace(':', '_')}"

    def _run_command(self, command: list[str]) -> bool:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, errors="replace")
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("Command failed: {} stderr={}", " ".join(command), (exc.stderr or "").strip())
            return False

    def _block_windows(self, ip: str) -> bool:
        rule_name = self._rule_name(ip)
        return self._run_command(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={rule_name}",
                "dir=in",
                "action=block",
                f"remoteip={ip}",
                "enable=yes",
            ]
        )

    def _unblock_windows(self, ip: str) -> bool:
        rule_name = self._rule_name(ip)
        return self._run_command(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "delete",
                "rule",
                f"name={rule_name}",
            ]
        )

    def _block_linux(self, ip: str) -> bool:
        return self._run_command(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"])

    def _unblock_linux(self, ip: str) -> bool:
        return self._run_command(["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"])

    def block_ip(self, ip: str, duration_seconds: int = 600) -> bool:
        if not _is_valid_ip(ip):
            logger.warning("Refusing to block invalid IP: {}", ip)
            return False

        blocked = False

        if self._platform.startswith("win"):
            blocked = self._block_windows(ip)
        elif self._platform.startswith("linux"):
            blocked = self._block_linux(ip)
        else:
            logger.warning("Unsupported platform for automatic blocking: {}", self._platform)
            return False

        if not blocked:
            return False

        logger.warning("Blocked IP {} for {} seconds", ip, duration_seconds)
        timer = threading.Timer(duration_seconds, self.unblock_ip, args=[ip])
        timer.daemon = True
        timer.start()
        return True

    def unblock_ip(self, ip: str) -> bool:
        if not _is_valid_ip(ip):
            logger.warning("Refusing to unblock invalid IP: {}", ip)
            return False

        if self._platform.startswith("win"):
            ok = self._unblock_windows(ip)
        elif self._platform.startswith("linux"):
            ok = self._unblock_linux(ip)
        else:
            logger.warning("Unsupported platform for automatic unblocking: {}", self._platform)
            return False

        if ok:
            logger.info("Unblocked IP {}", ip)
        return ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-IDS IP defender")
    parser.add_argument("--test-block", type=str, default=None, help="IP to block for test")
    parser.add_argument("--duration", type=int, default=60, help="Test block duration seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.test_block:
        return

    blocker = IPBlocker()
    ok = blocker.block_ip(args.test_block, args.duration)
    if not ok:
        raise SystemExit(1)

    logger.info("Waiting {} seconds before auto-unblock", args.duration)
    time.sleep(args.duration + 1)


if __name__ == "__main__":
    main()
