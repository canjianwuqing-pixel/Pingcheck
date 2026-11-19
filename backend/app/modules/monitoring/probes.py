import asyncio
import errno
import os
import re
import socket
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Literal


ProbeOutcome = Literal["success", "failure", "unknown"]


@dataclass(frozen=True)
class ProbeResult:
    outcome: ProbeOutcome
    latency_ms: float | None
    message: str | None = None


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


async def probe_tcp(ip: str, port: int, timeout: float) -> ProbeResult:
    started_at = time.perf_counter()
    writer: asyncio.StreamWriter | None = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        return ProbeResult("success", _elapsed_ms(started_at))
    except TimeoutError:
        return ProbeResult("failure", _elapsed_ms(started_at), "连接超时")
    except ConnectionRefusedError:
        return ProbeResult("failure", _elapsed_ms(started_at), "连接被拒绝")
    except OSError as error:
        return ProbeResult(
            "failure", _elapsed_ms(started_at), f"连接失败：{error}"
        )
    finally:
        if writer is not None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()


def _is_udp_port_unreachable(error: OSError) -> bool:
    error_code = getattr(error, "winerror", None) or error.errno
    return isinstance(error, (ConnectionRefusedError, ConnectionResetError)) or error_code in {
        errno.ECONNREFUSED,
        errno.ECONNRESET,
        10054,
        10061,
    }


async def probe_udp(ip: str, port: int, timeout: float) -> ProbeResult:
    address = ip_address(ip)
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    destination = (ip, port, 0, 0) if address.version == 6 else (ip, port)
    udp_socket = socket.socket(family, socket.SOCK_DGRAM)
    udp_socket.setblocking(False)
    loop = asyncio.get_running_loop()
    started_at = time.perf_counter()

    try:
        udp_socket.connect(destination)
        await loop.sock_sendall(udp_socket, b"PINGCHECK")
        await asyncio.wait_for(loop.sock_recv(udp_socket, 2048), timeout=timeout)
        return ProbeResult("success", _elapsed_ms(started_at), "收到 UDP 响应")
    except TimeoutError:
        return ProbeResult("unknown", None, "未收到 UDP 响应")
    except OSError as error:
        if _is_udp_port_unreachable(error):
            return ProbeResult(
                "failure", _elapsed_ms(started_at), "UDP 端口明确不可达"
            )
        return ProbeResult("unknown", None, f"UDP 探测结果未知：{error}")
    finally:
        udp_socket.close()


def _icmp_command(ip: str, timeout: float) -> list[str]:
    version_flag = "-6" if ip_address(ip).version == 6 else "-4"
    if sys.platform == "win32":
        return [
            "ping",
            version_flag,
            "-n",
            "1",
            "-w",
            str(max(1, int(timeout * 1000))),
            ip,
        ]
    return ["ping", version_flag, "-n", "-c", "1", "-W", str(timeout), ip]


async def _run_icmp_command(
    command: list[str], timeout: float
) -> tuple[int, bytes]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=environment,
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(), timeout=timeout + 1
        )
    except TimeoutError:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    return process.returncode or 0, output


def _parse_icmp_latency(output: bytes) -> float | None:
    text = output.decode(errors="ignore")
    match = re.search(
        r"([=<])\s*([0-9]+(?:[.,][0-9]+)?)\s*ms", text, re.IGNORECASE
    )
    if match is None:
        return None
    value = float(match.group(2).replace(",", "."))
    return round(value / 2, 2) if match.group(1) == "<" else round(value, 2)


async def probe_icmp(ip: str, timeout: float) -> ProbeResult:
    started_at = time.perf_counter()
    try:
        return_code, output = await _run_icmp_command(
            _icmp_command(ip, timeout), timeout
        )
    except TimeoutError:
        return ProbeResult("failure", None, "ICMP Ping 超时")
    except FileNotFoundError:
        return ProbeResult("failure", None, "系统 Ping 命令不可用")
    except PermissionError:
        return ProbeResult("failure", None, "缺少 ICMP Ping 权限")
    except OSError:
        return ProbeResult("failure", None, "ICMP Ping 执行失败")

    if return_code == 0:
        latency = _parse_icmp_latency(output)
        return ProbeResult(
            "success",
            latency if latency is not None else _elapsed_ms(started_at),
            "收到 ICMP 回复",
        )
    if return_code == 1:
        return ProbeResult("failure", None, "ICMP Ping 超时或不可达")
    return ProbeResult("failure", None, "ICMP Ping 执行失败")


async def probe_target(
    protocol: str, ip: str, port: int | None, timeout: float
) -> ProbeResult:
    if protocol == "ICMP":
        return await probe_icmp(ip, timeout)
    if port is None:
        return ProbeResult("failure", None, "端口配置缺失")
    if protocol == "TCP":
        return await probe_tcp(ip, port, timeout)
    return await probe_udp(ip, port, timeout)
