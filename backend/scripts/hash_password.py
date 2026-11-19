import getpass
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402


def main() -> None:
    password = getpass.getpass("请输入新的管理密码：")
    confirmation = getpass.getpass("请再次输入：")
    if not password:
        raise SystemExit("密码不能为空")
    if password != confirmation:
        raise SystemExit("两次输入不一致")
    print(hash_password(password))


if __name__ == "__main__":
    main()
