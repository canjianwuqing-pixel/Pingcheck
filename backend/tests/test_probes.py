import asyncio
import errno

from app.modules.monitoring import probes
from app.modules.monitoring.probes import (
    _is_udp_port_unreachable,
    probe_icmp,
    probe_target,
    probe_tcp,
    probe_udp,
)


class EchoProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, address) -> None:
        self.transport.sendto(b"pong", address)


class SilentProtocol(asyncio.DatagramProtocol):
    pass


def test_tcp_probe_records_success_and_failure() -> None:
    async def scenario() -> None:
        server = await asyncio.start_server(
            lambda reader, writer: writer.close(), "127.0.0.1", 0
        )
        port = server.sockets[0].getsockname()[1]

        success = await probe_tcp("127.0.0.1", port, 0.5)
        server.close()
        await server.wait_closed()
        failure = await probe_tcp("127.0.0.1", port, 0.5)

        assert success.outcome == "success"
        assert success.latency_ms is not None
        assert failure.outcome == "failure"
        assert failure.latency_ms is not None

    asyncio.run(scenario())


def test_udp_probe_distinguishes_response_and_no_response() -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        echo_transport, _ = await loop.create_datagram_endpoint(
            EchoProtocol, local_addr=("127.0.0.1", 0)
        )
        echo_port = echo_transport.get_extra_info("sockname")[1]
        response = await probe_udp("127.0.0.1", echo_port, 0.5)
        echo_transport.close()

        silent_transport, _ = await loop.create_datagram_endpoint(
            SilentProtocol, local_addr=("127.0.0.1", 0)
        )
        silent_port = silent_transport.get_extra_info("sockname")[1]
        no_response = await probe_udp("127.0.0.1", silent_port, 0.05)
        silent_transport.close()

        assert response.outcome == "success"
        assert response.latency_ms is not None
        assert no_response.outcome == "unknown"
        assert no_response.latency_ms is None

    asyncio.run(scenario())


def test_udp_unreachable_error_classification() -> None:
    error = ConnectionRefusedError(errno.ECONNREFUSED, "port unreachable")
    assert _is_udp_port_unreachable(error) is True


def test_icmp_probe_uses_echo_reply_and_supports_ipv4_ipv6(monkeypatch) -> None:
    commands: list[list[str]] = []

    async def successful_ping(
        command: list[str], timeout: float
    ) -> tuple[int, bytes]:
        commands.append(command)
        return 0, b"64 bytes from host: icmp_seq=1 ttl=64 time=12.34 ms"

    monkeypatch.setattr(probes, "_run_icmp_command", successful_ping)

    async def scenario() -> None:
        ipv4 = await probe_icmp("127.0.0.1", 0.5)
        ipv6 = await probe_target("ICMP", "::1", None, 0.5)
        assert ipv4.outcome == "success"
        assert ipv4.latency_ms == 12.34
        assert ipv6.outcome == "success"
        assert ipv6.latency_ms == 12.34

    asyncio.run(scenario())
    assert commands[0][1] == "-4"
    assert commands[1][1] == "-6"
    assert all("-c" in command or "-n" in command for command in commands)


def test_icmp_timeout_and_command_failure_have_no_latency(monkeypatch) -> None:
    async def no_reply(
        command: list[str], timeout: float
    ) -> tuple[int, bytes]:
        return 1, b"1 packets transmitted, 0 received, 100% packet loss"

    monkeypatch.setattr(probes, "_run_icmp_command", no_reply)
    no_response = asyncio.run(probe_icmp("192.0.2.1", 0.1))
    assert no_response.outcome == "failure"
    assert no_response.latency_ms is None
    assert "超时或不可达" in (no_response.message or "")

    async def timed_out(command: list[str], timeout: float) -> tuple[int, bytes]:
        raise TimeoutError

    monkeypatch.setattr(probes, "_run_icmp_command", timed_out)
    timed_out_result = asyncio.run(probe_icmp("192.0.2.1", 0.1))
    assert timed_out_result.outcome == "failure"
    assert timed_out_result.latency_ms is None
    assert timed_out_result.message == "ICMP Ping 超时"
