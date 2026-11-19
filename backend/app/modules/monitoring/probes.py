import asyncio
import errno
import socket
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


async def probe_target(
    protocol: str, ip: str, port: int, timeout: float
) -> ProbeResult:
    if protocol == "TCP":
        return await probe_tcp(ip, port, timeout)
    return await probe_udp(ip, port, timeout)
