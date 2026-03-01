#!/usr/bin/env python3
"""
将 profile.json 上传到自托管 Solid Pod

用法:
  1. 启动自托管 Solid: docker compose -f docker-compose.solid.yml up -d
  2. 访问 https://localhost:8443 注册账号
  3. 配置环境变量后执行（二选一）:
     OAuth2 客户端凭证（推荐）:
       SOLID_CLIENT_ID=... SOLID_CLIENT_SECRET=... SOLID_POD_ENDPOINT=... SOLID_IDP=...
     或 用户名/密码（需 pip install open-a2a[solid]）:
       SOLID_IDP=... SOLID_POD_ENDPOINT=... SOLID_USERNAME=... SOLID_PASSWORD=...
     python example/upload_profile_to_solid.py

或: python example/upload_profile_to_solid.py --profile example/profile.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 支持从项目根目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="将 profile.json 上传到 Solid Pod")
    parser.add_argument(
        "--profile",
        default=Path(__file__).parent / "profile.json",
        type=Path,
        help="本地 profile.json 路径",
    )
    args = parser.parse_args()

    if not args.profile.exists():
        print(f"错误: 文件不存在 {args.profile}")
        sys.exit(1)

    with open(args.profile, encoding="utf-8") as f:
        data = json.load(f)

    try:
        from open_a2a import SolidPodPreferencesProvider

        provider = SolidPodPreferencesProvider()
        provider.save(data)
        pod = os.getenv("SOLID_POD_ENDPOINT", "").rstrip("/")
        print(f"已上传偏好到 Solid Pod: {pod}/open-a2a/profile.json")
    except ImportError as e:
        print(f"错误: 需要安装 solid-file: pip install open-a2a[solid]")
        sys.exit(1)
    except ValueError as e:
        print(f"错误: {e}")
        print("请设置环境变量: 客户端凭证 SOLID_CLIENT_ID/SOLID_CLIENT_SECRET 或 用户名/密码 SOLID_IDP/SOLID_USERNAME/SOLID_PASSWORD，以及 SOLID_POD_ENDPOINT")
        sys.exit(1)
    except Exception as e:
        print(f"上传失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
