"""Run the whole Sarbon24 stack locally with ONE command:

    py run_all.py

Starts the web admin + the driver bot + the auto-scraper together, and streams their logs.
Press Ctrl+C to stop all three. Uses your .env (SQLite by default).
"""
import subprocess
import sys
import time

CMDS = [
    ("web      ", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]),
    ("bot      ", [sys.executable, "-m", "app.bot.main"]),
    ("scheduler", [sys.executable, "-m", "app.scheduler"]),
]


def main():
    procs = []
    for name, cmd in CMDS:
        print(f"starting {name.strip()} ...")
        procs.append((name, subprocess.Popen(cmd)))
    print("\n✅ All started.  Web admin: http://127.0.0.1:8000")
    print("   Press Ctrl+C to stop everything.\n")
    try:
        while True:
            time.sleep(1)
            for name, p in procs:
                if p.poll() is not None:
                    print(f"[{name.strip()}] exited (code {p.returncode})")
    except KeyboardInterrupt:
        print("\nstopping all...")
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


if __name__ == "__main__":
    main()
