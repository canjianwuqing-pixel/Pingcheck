import asyncio
import errno

from app.modules.monitoring.probes import (
    _is_udp_port_unreachable,
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
