import argparse
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import requests
from loguru import logger
from scapy.all import IP, TCP, UDP, Raw, sniff

try:
    from agent.defender import IPBlocker
except ModuleNotFoundError:
    from defender import IPBlocker


FEATURE_COLUMNS = [
    "duration",
    "protocol_type",
    "service",
    "flag",
    "src_bytes",
    "dst_bytes",
    "land",
    "wrong_fragment",
    "urgent",
    "hot",
    "num_failed_logins",
    "logged_in",
    "num_compromised",
    "root_shell",
    "su_attempted",
    "num_root",
    "num_file_creations",
    "num_shells",
    "num_access_files",
    "num_outbound_cmds",
    "is_host_login",
    "is_guest_login",
    "count",
    "srv_count",
    "serror_rate",
    "srv_serror_rate",
    "rerror_rate",
    "srv_rerror_rate",
    "same_srv_rate",
    "diff_srv_rate",
    "srv_diff_host_rate",
    "dst_host_count",
    "dst_host_srv_count",
    "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate",
    "dst_host_srv_serror_rate",
    "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]

CATEGORICAL_COLUMNS = ["protocol_type", "service", "flag"]
NUMERIC_COLUMNS = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]

SHORT_WINDOW_SECONDS = 2.0
LONG_WINDOW_SECONDS = 60.0
FLOW_TTL_SECONDS = 300.0
MAX_FLOW_STATES = 50000
MAX_SHORT_EVENTS = max(2000, int(os.getenv("MAX_SHORT_EVENTS", "40000")))
MAX_LONG_EVENTS = max(5000, int(os.getenv("MAX_LONG_EVENTS", "200000")))
ALERT_URL = os.getenv("ALERT_ENDPOINT", "http://127.0.0.1:8000/alerts").strip()
BLOCK_THRESHOLD = float(os.getenv("BLOCK_THRESHOLD", "0.95"))
BLOCK_DURATION_SECONDS = int(os.getenv("BLOCK_DURATION_SECONDS", "600"))

SERROR_FLAGS = {"S0", "S1", "S2", "S3"}
RERROR_FLAGS = {"REJ", "RSTO", "RSTR"}

SERVICE_MAP = {
    20: "ftp_data",
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "domain",
    67: "dhcp",
    68: "dhcp",
    69: "tftp_u",
    80: "http",
    110: "pop_3",
    111: "sunrpc",
    119: "nnsp",
    123: "ntp_u",
    135: "remote_job",
    137: "netbios_ns",
    138: "netbios_dgm",
    139: "netbios_ssn",
    143: "imap4",
    161: "snmp",
    162: "snmptrap",
    389: "ldap",
    443: "http_443",
    445: "microsoft_ds",
    514: "shell",
    515: "printer",
    543: "klogin",
    544: "kshell",
    993: "imap4",
    995: "pop_3",
    1433: "sql_net",
    1521: "sql_net",
    3306: "sql_net",
    3389: "remote_job",
    5432: "sql_net",
    5900: "X11",
    6379: "other",
    8080: "http",
}

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*([^\s;&,\"']+)"),
    re.compile(r"(?i)(token|access_token|refresh_token|auth_token)\s*[:=]\s*([^\s;&,\"']+)"),
    re.compile(r"(?i)(cookie)\s*[:=]\s*([^\r\n]+)"),
    re.compile(r"(?i)(authorization\s*:\s*bearer)\s+([^\s]+)"),
]


@dataclass
class FlowState:
    start_time: float
    last_seen: float
    src_bytes: int = 0


class RuntimeState:
    def __init__(self) -> None:
        self.flows: dict[tuple[str, str, int, int, str], FlowState] = {}
        self.short_events: deque[dict[str, Any]] = deque(maxlen=MAX_SHORT_EVENTS)
        self.long_events: deque[dict[str, Any]] = deque(maxlen=MAX_LONG_EVENTS)

    def prune(self, now_ts: float) -> None:
        while self.short_events and now_ts - self.short_events[0]["ts"] > SHORT_WINDOW_SECONDS:
            self.short_events.popleft()
        while self.long_events and now_ts - self.long_events[0]["ts"] > LONG_WINDOW_SECONDS:
            self.long_events.popleft()

        stale_keys = [
            key
            for key, flow in self.flows.items()
            if now_ts - flow.last_seen > FLOW_TTL_SECONDS
        ]
        for key in stale_keys:
            del self.flows[key]

        if len(self.flows) > MAX_FLOW_STATES:
            overflow = len(self.flows) - MAX_FLOW_STATES
            oldest_keys = sorted(
                self.flows,
                key=lambda key: self.flows[key].last_seen,
            )[:overflow]
            for key in oldest_keys:
                del self.flows[key]


def load_training_frame(csv_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, header=None)
    if frame.shape[1] == 43:
        frame.columns = FEATURE_COLUMNS + ["label", "difficulty"]
    elif frame.shape[1] == 42:
        frame.columns = FEATURE_COLUMNS + ["label"]
    else:
        raise ValueError(f"Unexpected NSL-KDD columns: {frame.shape[1]}")
    return frame


def build_encoder_maps(csv_path: Path) -> dict[str, dict[str, int]]:
    frame = load_training_frame(csv_path)
    maps: dict[str, dict[str, int]] = {}
    for column in CATEGORICAL_COLUMNS:
        unique_values = sorted(frame[column].astype(str).unique().tolist())
        maps[column] = {value: index for index, value in enumerate(unique_values)}
    return maps


def mask_payload(payload_bytes: bytes) -> str:
    if not payload_bytes:
        return ""

    text = payload_bytes.decode("utf-8", errors="replace")
    masked = text

    for pattern in SENSITIVE_PATTERNS:
        masked = pattern.sub(lambda m: f"{m.group(1)}=***MASKED***", masked)

    return masked[:512]


def protocol_name(packet: Any) -> str:
    if TCP in packet:
        return "tcp"
    if UDP in packet:
        return "udp"
    proto_number = int(packet[IP].proto)
    if proto_number == 1:
        return "icmp"
    return "tcp"


def service_name(proto: str, dst_port: int) -> str:
    if proto == "icmp":
        return "eco_i"
    if dst_port in SERVICE_MAP:
        return SERVICE_MAP[dst_port]
    return "other"


def flag_name(packet: Any) -> str:
    if TCP not in packet:
        return "SF"

    tcp_flags = int(packet[TCP].flags)
    syn = bool(tcp_flags & 0x02)
    ack = bool(tcp_flags & 0x10)
    rst = bool(tcp_flags & 0x04)
    fin = bool(tcp_flags & 0x01)

    if rst and ack:
        return "RSTR"
    if rst:
        return "RSTO"
    if syn and not ack:
        return "S0"
    if syn and ack:
        return "S1"
    if fin and ack:
        return "SF"
    return "OTH"


def count_ratio(values: list[dict[str, Any]], predicate) -> float:
    if not values:
        return 0.0
    return sum(1 for item in values if predicate(item)) / len(values)


def encode_categorical(
    column: str,
    value: str,
    encoder_maps: dict[str, dict[str, int]],
) -> int:
    mapping = encoder_maps[column]
    if value in mapping:
        return mapping[value]
    if "other" in mapping:
        return mapping["other"]
    return 0


def extract_features(
    packet: Any,
    state: RuntimeState,
    encoder_maps: dict[str, dict[str, int]],
    scaler: Any,
) -> tuple[pd.DataFrame, dict[str, float], str, str, str] | None:
    if IP not in packet:
        return None

    ip_layer = packet[IP]
    src_ip = ip_layer.src
    dst_ip = ip_layer.dst
    protocol = protocol_name(packet)

    src_port = int(packet.sport) if hasattr(packet, "sport") else 0
    dst_port = int(packet.dport) if hasattr(packet, "dport") else 0

    service = service_name(protocol, dst_port)
    flag = flag_name(packet)

    payload_bytes = bytes(packet[Raw].load) if Raw in packet else b""
    masked_payload = mask_payload(payload_bytes)

    now_ts = time.time()
    state.prune(now_ts)

    flow_key = (src_ip, dst_ip, src_port, dst_port, protocol)
    reverse_key = (dst_ip, src_ip, dst_port, src_port, protocol)

    if flow_key not in state.flows:
        state.flows[flow_key] = FlowState(start_time=now_ts, last_seen=now_ts)

    packet_len = len(payload_bytes) if payload_bytes else len(bytes(packet))
    state.flows[flow_key].src_bytes += packet_len
    state.flows[flow_key].last_seen = now_ts

    src_bytes = state.flows[flow_key].src_bytes
    dst_bytes = state.flows[reverse_key].src_bytes if reverse_key in state.flows else 0
    duration = now_ts - state.flows[flow_key].start_time

    payload_lower = masked_payload.lower()

    event = {
        "ts": now_ts,
        "dst_host": dst_ip,
        "service": service,
        "flag": flag,
        "src_port": src_port,
    }
    state.short_events.append(event)
    state.long_events.append(event)

    short_host_events = [e for e in state.short_events if e["dst_host"] == dst_ip]
    short_service_events = [e for e in short_host_events if e["service"] == service]

    count = len(short_host_events)
    srv_count = len(short_service_events)
    same_srv_rate = (srv_count / count) if count else 0.0

    service_window_events = [e for e in state.short_events if e["service"] == service]

    long_host_events = [e for e in state.long_events if e["dst_host"] == dst_ip]
    long_host_service_events = [e for e in long_host_events if e["service"] == service]
    long_service_events = [e for e in state.long_events if e["service"] == service]

    dst_host_count = len(long_host_events)
    dst_host_srv_count = len(long_host_service_events)

    numeric_values = {
        "duration": duration,
        "src_bytes": float(src_bytes),
        "dst_bytes": float(dst_bytes),
        "land": float(int(src_ip == dst_ip and src_port == dst_port)),
        "wrong_fragment": float(int(ip_layer.frag > 0)),
        "urgent": float(int(TCP in packet and int(packet[TCP].urgptr) > 0)),
        "hot": float(sum(payload_lower.count(word) for word in ["cmd", "root", "attack", "sudo"])),
        "num_failed_logins": float(len(re.findall(r"failed\s+login|auth\s+failed", payload_lower))),
        "logged_in": float(int("login successful" in payload_lower or "logged in" in payload_lower)),
        "num_compromised": float(sum(payload_lower.count(word) for word in ["compromise", "exploit", "overflow"])),
        "root_shell": float(int("root shell" in payload_lower or "uid=0" in payload_lower)),
        "su_attempted": float(int(" su " in f" {payload_lower} " or "sudo" in payload_lower)),
        "num_root": float(payload_lower.count("uid=0")),
        "num_file_creations": float(len(re.findall(r"create\s+file|touch\s+", payload_lower))),
        "num_shells": float(len(re.findall(r"/bin/sh|sh\s+-c|powershell", payload_lower))),
        "num_access_files": float(len(re.findall(r"open\(|read\(|write\(", payload_lower))),
        "num_outbound_cmds": 0.0,
        "is_host_login": float(int("host login" in payload_lower)),
        "is_guest_login": float(int("guest" in payload_lower)),
        "count": float(count),
        "srv_count": float(srv_count),
        "serror_rate": count_ratio(short_host_events, lambda e: e["flag"] in SERROR_FLAGS),
        "srv_serror_rate": count_ratio(short_service_events, lambda e: e["flag"] in SERROR_FLAGS),
        "rerror_rate": count_ratio(short_host_events, lambda e: e["flag"] in RERROR_FLAGS),
        "srv_rerror_rate": count_ratio(short_service_events, lambda e: e["flag"] in RERROR_FLAGS),
        "same_srv_rate": same_srv_rate,
        "diff_srv_rate": 1.0 - same_srv_rate if count else 0.0,
        "srv_diff_host_rate": count_ratio(service_window_events, lambda e: e["dst_host"] != dst_ip),
        "dst_host_count": float(dst_host_count),
        "dst_host_srv_count": float(dst_host_srv_count),
        "dst_host_same_srv_rate": (dst_host_srv_count / dst_host_count) if dst_host_count else 0.0,
        "dst_host_diff_srv_rate": 1.0 - ((dst_host_srv_count / dst_host_count) if dst_host_count else 0.0),
        "dst_host_same_src_port_rate": count_ratio(long_host_events, lambda e: e["src_port"] == src_port),
        "dst_host_srv_diff_host_rate": count_ratio(long_service_events, lambda e: e["dst_host"] != dst_ip),
        "dst_host_serror_rate": count_ratio(long_host_events, lambda e: e["flag"] in SERROR_FLAGS),
        "dst_host_srv_serror_rate": count_ratio(long_host_service_events, lambda e: e["flag"] in SERROR_FLAGS),
        "dst_host_rerror_rate": count_ratio(long_host_events, lambda e: e["flag"] in RERROR_FLAGS),
        "dst_host_srv_rerror_rate": count_ratio(long_host_service_events, lambda e: e["flag"] in RERROR_FLAGS),
    }

    categorical_values = {
        "protocol_type": encode_categorical("protocol_type", protocol, encoder_maps),
        "service": encode_categorical("service", service, encoder_maps),
        "flag": encode_categorical("flag", flag, encoder_maps),
    }

    scaled_numeric = scaler.transform(pd.DataFrame([numeric_values], columns=NUMERIC_COLUMNS))[0]
    scaled_numeric_map = {
        feature_name: float(value)
        for feature_name, value in zip(NUMERIC_COLUMNS, scaled_numeric)
    }

    model_row = {
        **categorical_values,
        **scaled_numeric_map,
    }

    ordered_row = {feature: model_row[feature] for feature in FEATURE_COLUMNS}
    model_input = pd.DataFrame([ordered_row], columns=FEATURE_COLUMNS)

    feature_values = {
        "duration": numeric_values["duration"],
        "protocol_type": protocol,
        "service": service,
        "flag": flag,
        "src_bytes": numeric_values["src_bytes"],
        "dst_bytes": numeric_values["dst_bytes"],
        "land": numeric_values["land"],
        "wrong_fragment": numeric_values["wrong_fragment"],
        "urgent": numeric_values["urgent"],
        "hot": numeric_values["hot"],
        "num_failed_logins": numeric_values["num_failed_logins"],
        "logged_in": numeric_values["logged_in"],
        "num_compromised": numeric_values["num_compromised"],
        "root_shell": numeric_values["root_shell"],
        "su_attempted": numeric_values["su_attempted"],
        "num_root": numeric_values["num_root"],
        "num_file_creations": numeric_values["num_file_creations"],
        "num_shells": numeric_values["num_shells"],
        "num_access_files": numeric_values["num_access_files"],
        "num_outbound_cmds": numeric_values["num_outbound_cmds"],
        "is_host_login": numeric_values["is_host_login"],
        "is_guest_login": numeric_values["is_guest_login"],
        "count": numeric_values["count"],
        "srv_count": numeric_values["srv_count"],
        "serror_rate": numeric_values["serror_rate"],
        "srv_serror_rate": numeric_values["srv_serror_rate"],
        "rerror_rate": numeric_values["rerror_rate"],
        "srv_rerror_rate": numeric_values["srv_rerror_rate"],
        "same_srv_rate": numeric_values["same_srv_rate"],
        "diff_srv_rate": numeric_values["diff_srv_rate"],
        "srv_diff_host_rate": numeric_values["srv_diff_host_rate"],
        "dst_host_count": numeric_values["dst_host_count"],
        "dst_host_srv_count": numeric_values["dst_host_srv_count"],
        "dst_host_same_srv_rate": numeric_values["dst_host_same_srv_rate"],
        "dst_host_diff_srv_rate": numeric_values["dst_host_diff_srv_rate"],
        "dst_host_same_src_port_rate": numeric_values["dst_host_same_src_port_rate"],
        "dst_host_srv_diff_host_rate": numeric_values["dst_host_srv_diff_host_rate"],
        "dst_host_serror_rate": numeric_values["dst_host_serror_rate"],
        "dst_host_srv_serror_rate": numeric_values["dst_host_srv_serror_rate"],
        "dst_host_rerror_rate": numeric_values["dst_host_rerror_rate"],
        "dst_host_srv_rerror_rate": numeric_values["dst_host_srv_rerror_rate"],
    }

    return model_input, feature_values, src_ip, dst_ip, masked_payload


def send_anomaly(
    src_ip: str,
    dst_ip: str,
    payload: str,
    feature_values: dict[str, float],
    model_probability: float,
    blocked: bool,
    block_expires_at: float | None,
) -> None:
    body = {
        "event": "anomaly",
        "source_ip": src_ip,
        "destination_ip": dst_ip,
        "payload": payload,
        "timestamp": time.time(),
        "feature_values": feature_values,
        "model_probability": model_probability,
        "blocked": blocked,
        "block_expires_at": block_expires_at,
    }
    try:
        response = requests.post(ALERT_URL, json=body, timeout=2)
        if response.status_code >= 400:
            logger.warning("Alert endpoint returned status {}", response.status_code)
    except requests.RequestException as exc:
        logger.warning("Failed to send anomaly to {}: {}", ALERT_URL, exc)


def start_sniffer(iface: str | None, dry_run: bool, force_block_on_dry_run: bool) -> None:
    root_dir = Path(__file__).resolve().parents[1]
    model = joblib.load(root_dir / "models" / "rf_model.pkl")
    scaler = joblib.load(root_dir / "models" / "scaler.pkl")
    encoder_maps = build_encoder_maps(root_dir / "data" / "KDDTrain.csv")
    blocker = IPBlocker()

    state = RuntimeState()

    def handle_packet(packet: Any) -> None:
        extracted = extract_features(packet, state, encoder_maps, scaler)
        if extracted is None:
            return

        model_input, feature_values, src_ip, dst_ip, masked_payload = extracted
        prediction = int(model.predict(model_input)[0])
        probability = float(model.predict_proba(model_input)[0][1])

        if force_block_on_dry_run and dry_run:
            probability = 1.0
            prediction = 1

        blocked = False
        block_expires_at: float | None = None
        if probability > BLOCK_THRESHOLD:
            blocked = blocker.block_ip(src_ip, BLOCK_DURATION_SECONDS)
            if blocked:
                block_expires_at = time.time() + BLOCK_DURATION_SECONDS

        if prediction == 1:
            logger.warning(
                "异常流量 src={} dst={} prob={:.6f} blocked={} payload={}",
                src_ip,
                dst_ip,
                probability,
                blocked,
                masked_payload,
            )
            send_anomaly(
                src_ip=src_ip,
                dst_ip=dst_ip,
                payload=masked_payload,
                feature_values=feature_values,
                model_probability=probability,
                blocked=blocked,
                block_expires_at=block_expires_at,
            )

    if dry_run:
        sample_packet = (
            IP(src="10.0.0.10", dst="10.0.0.20")
            / TCP(sport=44444, dport=80, flags="PA")
            / Raw(load=b"username=alice&password=supersecret&token=abc123")
        )
        handle_packet(sample_packet)
        logger.info("Dry run completed.")
        return

    logger.info("Starting packet sniffer on iface={}", iface or "default")
    sniff(filter="ip", iface=iface, prn=handle_packet, store=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-IDS packet sniffer agent")
    parser.add_argument("--iface", type=str, default=None, help="Network interface name")
    parser.add_argument("--dry-run", action="store_true", help="Run one synthetic packet")
    parser.add_argument(
        "--force-block-on-dry-run",
        action="store_true",
        help="Force probability=1.0 in dry-run to validate block flow",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        start_sniffer(
            iface=args.iface,
            dry_run=args.dry_run,
            force_block_on_dry_run=args.force_block_on_dry_run,
        )
    except PermissionError:
        logger.error("Permission denied. Please run as Administrator/root.")
        raise
    except Exception as exc:
        logger.exception("Sniffer failed: {}", exc)
        raise


if __name__ == "__main__":
    main()
