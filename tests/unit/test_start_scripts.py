import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class StartScriptsTests(unittest.TestCase):
    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding='utf-8')
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def test_start_api_gateway_loads_root_env_file(self) -> None:
        repo_root = Path(tempfile.mkdtemp(prefix='quant-start-api-'))
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        scripts_dir = repo_root / 'scripts'
        scripts_dir.mkdir(parents=True, exist_ok=True)

        source_script = Path('/home/luuuu/miniconda3/envs/new-auto-trading/scripts/start_api_gateway.sh')
        shutil.copy2(source_script, scripts_dir / 'start_api_gateway.sh')

        (repo_root / '.env').write_text(
            'QUANT_API_HOST=127.0.0.9\nQUANT_API_PORT=19999\n',
            encoding='utf-8',
        )

        fake_bin = repo_root / 'fake-bin'
        fake_bin.mkdir(parents=True, exist_ok=True)
        self._write_executable(
            fake_bin / 'uvicorn',
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                echo "HOST=$QUANT_API_HOST"
                echo "PORT=$QUANT_API_PORT"
                """
            ),
        )

        env = os.environ.copy()
        env['PATH'] = f"{fake_bin}:{env['PATH']}"
        result = subprocess.run(
            ['bash', str(scripts_dir / 'start_api_gateway.sh')],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('HOST=127.0.0.9', result.stdout)
        self.assertIn('PORT=19999', result.stdout)

    def test_start_scheduler_loads_root_env_file(self) -> None:
        repo_root = Path(tempfile.mkdtemp(prefix='quant-start-scheduler-'))
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        scripts_dir = repo_root / 'scripts'
        scripts_dir.mkdir(parents=True, exist_ok=True)

        source_script = Path('/home/luuuu/miniconda3/envs/new-auto-trading/scripts/start_scheduler.sh')
        shutil.copy2(source_script, scripts_dir / 'start_scheduler.sh')

        (repo_root / '.env').write_text(
            'QUANT_MARKET_DATA_PROVIDER=mock\nQUANT_SQLITE_PATH=data/custom.sqlite3\n',
            encoding='utf-8',
        )

        fake_bin = repo_root / 'fake-bin'
        fake_bin.mkdir(parents=True, exist_ok=True)
        self._write_executable(
            fake_bin / 'python',
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                echo "PROVIDER=$QUANT_MARKET_DATA_PROVIDER"
                echo "SQLITE=$QUANT_SQLITE_PATH"
                """
            ),
        )

        env = os.environ.copy()
        env['PATH'] = f"{fake_bin}:{env['PATH']}"
        result = subprocess.run(
            ['bash', str(scripts_dir / 'start_scheduler.sh')],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('PROVIDER=mock', result.stdout)
        self.assertIn('SQLITE=data/custom.sqlite3', result.stdout)


if __name__ == '__main__':
    unittest.main()
