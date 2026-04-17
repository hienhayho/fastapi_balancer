import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        dashboard_dir = root / "dashboard"
        dist_dir = dashboard_dir / "dist"
        target_dir = root / "fastapi_balancer" / "dashboard_dist"

        if not dashboard_dir.is_dir():
            self.app.display_warning("dashboard/ directory not found — skipping frontend build")
            return

        self.app.display_info("Building frontend dashboard ...")
        try:
            subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=dashboard_dir, check=True)
            subprocess.run(["pnpm", "build"], cwd=dashboard_dir, check=True)
        except FileNotFoundError:
            self.app.display_warning("pnpm not found — skipping frontend build")
            return
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Frontend build failed: {e}") from e

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(dist_dir, target_dir)
        self.app.display_info(f"Frontend build copied to {target_dir}")
