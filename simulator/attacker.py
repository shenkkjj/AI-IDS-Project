import argparse
import os
import random
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import requests
from loguru import logger
from scapy.all import IP, TCP, send, sr1


DEFAULT_SCAN_PORTS = [
    21,
    22,
    23,
    25,
    53,
    80,
    110,
    135,
    139,
    143,
    443,
    445,
    1433,
    1521,
    3306,
    3389,
    5432,
    6379,
    8080,
]

AWVS_USER_AGENT = os.getenv("ATTACKER_USER_AGENT", "AWVS/14.7 Acunetix").strip()


@dataclass(frozen=True)
class AttackRequest:
    name: str
    method: str
    path: str
    params: dict[str, str] | None = None
    data: dict[str, str] | None = None


@dataclass(frozen=True)
class PortProbeResult:
    port: int
    status: str


def post_alert(alert_endpoint: str, source_ip: str, destination_ip: str, payload: str) -> None:
    body = {
        "event": "anomaly",
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "payload": payload,
        "timestamp": time.time(),
    }
    try:
        response = requests.post(alert_endpoint, json=body, timeout=3)
        if response.status_code >= 400:
            logger.warning("告警上报失败 status={} body={}", response.status_code, response.text[:200])
    except requests.RequestException as exc:
        logger.warning("告警上报异常 endpoint={} err={}", alert_endpoint, exc)


def simulate_syn_scan(target_ip: str, ports: list[int], delay_seconds: float) -> list[PortProbeResult]:
    logger.info("[Phase 1] 开始模拟 Nmap 隐蔽 SYN 扫描 target={} ports={}", target_ip, ports)
    probe_results: list[PortProbeResult] = []

    for port in random.sample(ports, len(ports)):
        source_port = random.randint(1024, 65535)
        sequence = random.randint(1, 2**32 - 1)
        syn_packet = IP(dst=target_ip) / TCP(
            sport=source_port,
            dport=port,
            flags="S",
            seq=sequence,
            window=1024,
        )

        status = "filtered"
        response: Any = sr1(syn_packet, timeout=0.4, verbose=0)

        if response is not None and response.haslayer(TCP):
            flags = int(response[TCP].flags)
            if flags & 0x12 == 0x12:
                status = "open"
                rst_packet = IP(dst=target_ip) / TCP(
                    sport=source_port,
                    dport=port,
                    flags="R",
                    seq=response[TCP].ack,
                    ack=response[TCP].seq + 1,
                )
                send(rst_packet, verbose=False)
            elif flags & 0x14 == 0x14 or flags & 0x04:
                status = "closed"

        probe_results.append(PortProbeResult(port=port, status=status))
        logger.info("SYN probe dport={} status={}", port, status)
        time.sleep(delay_seconds)

    return probe_results


def build_nmap_signature_payload(target_ip: str, probe_results: list[PortProbeResult]) -> str:
    open_ports = [str(item.port) for item in probe_results if item.status == "open"]
    closed_ports = [str(item.port) for item in probe_results if item.status == "closed"]
    filtered_ports = [str(item.port) for item in probe_results if item.status == "filtered"]

    return "\n".join(
        [
            "[SIMULATOR] Nmap SYN Scan Signature",
            f"target={target_ip}",
            f"open_ports={','.join(open_ports) if open_ports else 'none'}",
            f"closed_ports={','.join(closed_ports) if closed_ports else 'none'}",
            f"filtered_ports={','.join(filtered_ports) if filtered_ports else 'none'}",
            "fingerprint=half-open SYN probes, immediate RST on SYN-ACK, multi-port sweep",
            "tool_hint=nmap -sS -Pn",
        ]
    )


def simulate_awvs_like_requests(target_base_url: str, delay_seconds: float) -> list[str]:
    logger.info("[Phase 2] 开始模拟 AWVS 漏扫流量 target={}", target_base_url)

    attack_requests = [
        AttackRequest(
            name="SQLi-UNION-GET",
            method="GET",
            path="/health",
            params={"id": "1 UNION SELECT username,password FROM users--"},
        ),
        AttackRequest(
            name="SQLi-Boolean-POST",
            method="POST",
            path="/login",
            data={"username": "admin' OR '1'='1", "password": "x"},
        ),
        AttackRequest(
            name="XSS-Reflected-GET",
            method="GET",
            path="/search",
            params={"q": "<script>alert('awvs-xss')</script>"},
        ),
        AttackRequest(
            name="XSS-POST-Comment",
            method="POST",
            path="/comment",
            data={"content": "<img src=x onerror=alert('awvs')>"},
        ),
    ]

    findings: list[str] = []
    headers = {
        "User-Agent": AWVS_USER_AGENT,
        "X-Scanner": "AWVS",
        "Accept": "*/*",
        "Connection": "close",
    }

    for attack in attack_requests:
        url = target_base_url.rstrip("/") + attack.path
        try:
            response = requests.request(
                method=attack.method,
                url=url,
                params=attack.params,
                data=attack.data,
                headers=headers,
                timeout=4,
                allow_redirects=False,
            )
            finding = f"{attack.name} {attack.method} {response.url} status={response.status_code}"
            logger.info("{}", finding)
            findings.append(finding)
        except requests.RequestException as exc:
            finding = f"{attack.name} {attack.method} {url} error={exc}"
            logger.warning("{}", finding)
            findings.append(finding)

        time.sleep(delay_seconds)

    return findings


def build_awvs_signature_payload(target_base_url: str, findings: list[str]) -> str:
    return "\n".join(
        [
            "[SIMULATOR] AWVS Web Vulnerability Scan Signature",
            f"target={target_base_url}",
            f"user_agent={AWVS_USER_AGENT}",
            "payload_markers=UNION SELECT, OR 1=1, <script>, onerror=alert",
            "tool_hint=Acunetix AWVS automated scanner",
            "requests=",
            *[f"- {item}" for item in findings],
        ]
    )


def parse_ports(ports_text: str) -> list[int]:
    if not ports_text.strip():
        return DEFAULT_SCAN_PORTS

    parsed_ports: list[int] = []
    for raw in ports_text.split(","):
        value = raw.strip()
        if not value:
            continue
        port = int(value)
        if port < 1 or port > 65535:
            raise ValueError(f"Invalid port: {port}")
        parsed_ports.append(port)

    if not parsed_ports:
        return DEFAULT_SCAN_PORTS

    return sorted(set(parsed_ports))


def infer_destination_ip(target_base_url: str, fallback: str) -> str:
    parsed = urlparse(target_base_url)
    return parsed.hostname or fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-IDS 自动化攻击模拟器")
    parser.add_argument("--target-ip", default="127.0.0.1", help="SYN扫描目标IP")
    parser.add_argument(
        "--target-base-url",
        default="http://127.0.0.1:8000",
        help="AWVS模拟请求目标后端地址",
    )
    parser.add_argument(
        "--alert-endpoint",
        default="http://127.0.0.1:8000/alerts",
        help="IDS告警接收地址",
    )
    parser.add_argument(
        "--ports",
        default=",".join(str(p) for p in DEFAULT_SCAN_PORTS),
        help="SYN扫描端口列表，逗号分隔",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.08,
        help="每次探测间隔秒数",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ports = parse_ports(args.ports)
    destination_ip = infer_destination_ip(args.target_base_url, args.target_ip)

    logger.info("攻击模拟器启动：target_ip={} target_base_url={}", args.target_ip, args.target_base_url)

    syn_results: list[PortProbeResult] = []
    try:
        syn_results = simulate_syn_scan(args.target_ip, ports, args.delay)
        nmap_payload = build_nmap_signature_payload(args.target_ip, syn_results)
        post_alert(args.alert_endpoint, "127.0.0.1", args.target_ip, nmap_payload)
    except PermissionError:
        logger.error("SYN 扫描需要管理员/root权限，请提权后重试。")
    except OSError as exc:
        logger.error("SYN 扫描失败（通常是原始套接字权限问题）: {}", exc)

    awvs_findings = simulate_awvs_like_requests(args.target_base_url, args.delay)
    awvs_payload = build_awvs_signature_payload(args.target_base_url, awvs_findings)
    post_alert(args.alert_endpoint, "127.0.0.1", destination_ip, awvs_payload)

    logger.success(
        "攻击模拟完成: syn_probes={} awvs_requests={}",
        len(syn_results),
        len(awvs_findings),
    )


if __name__ == "__main__":
    main()
