import json
import os
import tempfile
from pathlib import Path
from typing import Any


SUPPORTED_SS_METHODS = {
    "aes-128-gcm",
    "aes-256-gcm",
    "chacha20-ietf-poly1305",
}


class ShadowsocksConfigManager:
    def __init__(self, config_path: Path, local_port: int) -> None:
        self.config_path = config_path
        self.local_port = local_port

    def sync(self, configuration: dict[str, Any]) -> bool:
        if configuration["proxy_type"] != "ss":
            if self.config_path.exists():
                self.config_path.unlink()
                return True
            return False

        if (
            not configuration["ss_server"]
            or configuration["ss_port"] is None
            or not configuration["ss_password"]
            or configuration["ss_method"] not in SUPPORTED_SS_METHODS
        ):
            raise ValueError("incomplete Shadowsocks configuration")

        payload = {
            "server": configuration["ss_server"],
            "server_port": configuration["ss_port"],
            "password": configuration["ss_password"],
            "method": configuration["ss_method"],
            "local_address": "0.0.0.0",
            "local_port": self.local_port,
        }
        serialized = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
        if self.config_path.exists() and self.config_path.read_bytes() == serialized:
            return False

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.config_path.parent,
                prefix=".ss-config-",
                delete=False,
            ) as temporary:
                temporary.write(serialized)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            temporary_path.chmod(0o600)
            os.replace(temporary_path, self.config_path)
            self.config_path.chmod(0o600)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return True
