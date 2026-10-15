"""Shared process launcher for the run_*.py entry scripts. Each part runs as its own
process so you can restart one without touching the others."""
import subprocess
import sys
import time

WEB = ("web      ", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
BOT = ("bot      ", [sys.executable, "-m", "app.bot.main"])
SCHEDULER = ("scheduler", [sys.executable, "-m", "app.scheduler"])


def run(cmds, banner=""):
    procs = []
    for name, cmd in cmds:
        print(f"starting {name.strip()} ...")
        procs.append((name, subprocess.Popen(cmd)))
    if banner:
        print("\n" + banner)
    print("   Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
            for name, p in procs:
                if p.poll() is not None:
                    print(f"[{name.strip()}] exited (code {p.returncode})")
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        for _, p in procs:
            if p.poll() is None:
                p.terminate()
        for _, p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()
        print("stopped.")
