#!/usr/bin/env python3
"""Bounded video-only recording inside an existing omalab namespace."""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def arm_parent_death(parent_pid):
    # Linux: a killed recording helper must not leave its encoder orphaned in
    # a retained lab. SIGINT gives wf-recorder the normal finalization path.
    libc = ctypes.CDLL(None, use_errno=True)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if libc.prctl(1, signal.SIGINT, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "cannot arm recorder parent-death signal")
    if os.getppid() != parent_pid:
        os.kill(os.getpid(), signal.SIGINT)


def record(seconds):
    if os.environ.get("OMALAB_INSIDE") != "1" or not Path("/lab/meta.json").is_file():
        raise ValueError("recording must run through omalab record")
    for binary in ("wf-recorder", "ffprobe"):
        if shutil.which(binary) is None:
            raise ValueError(f"missing recording dependency: {binary}")
    with open("/lab/run/record.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("a recording or geometry change already owns this lab") from error
        interrupted = False

        def request_stop(_signum, _frame):
            nonlocal interrupted
            interrupted = True

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)
        with tempfile.TemporaryDirectory(prefix="record-", dir="/lab/tmp") as directory:
            video = Path(directory) / "capture.mp4"
            parent_pid = os.getpid()
            argv = ["wf-recorder", "-o", "LAB", "-f", str(video), "-y", "-r", "30",
                    "-x", "yuv420p", "-c", "libx264", "-p", "preset=veryfast", "-D"]
            with open("/lab/record.log", "ab", buffering=0) as log:
                process = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    pass_fds=(lock.fileno(),),
                    preexec_fn=lambda: arm_parent_death(parent_pid),
                )
                print(f"omalab: recording PID {process.pid}; maximum {seconds}s", file=sys.stderr, flush=True)
                forced = False
                try:
                    deadline = time.monotonic() + seconds
                    while process.poll() is None and not interrupted and time.monotonic() < deadline:
                        time.sleep(0.05)
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            forced = True
                            process.kill()
                    process.wait(timeout=5)
                    if forced or process.returncode != 0:
                        raise ValueError(f"recorder did not finalize cleanly (exit {process.returncode}); inspect record.log")
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=codec_name,width,height:format=duration", "-of", "json", str(video)],
                        capture_output=True, text=True, timeout=10,
                    )
                    if probe.returncode:
                        raise ValueError("recorded MP4 failed ffprobe validation; inspect record.log")
                    metadata = json.loads(probe.stdout)
                    streams = metadata.get("streams", [])
                    duration = float(metadata.get("format", {}).get("duration", 0))
                    if not streams or streams[0].get("codec_name") != "h264" or duration <= 0:
                        raise ValueError("recorded MP4 has no valid H.264 video or duration")
                    stream = streams[0]
                    if stream.get("width", 0) <= 0 or stream.get("height", 0) <= 0:
                        raise ValueError("recorded MP4 has invalid video dimensions")
                    print(f"omalab: recorder exited 0; verified {stream['width']}x{stream['height']} H.264, {duration:.2f}s", file=sys.stderr, flush=True)
                    with video.open("rb") as source:
                        shutil.copyfileobj(source, sys.stdout.buffer)
                    sys.stdout.buffer.flush()
                finally:
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.duration <= 300:
        parser.error("duration must be 1-300 seconds")
    record(args.duration)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"omalab record: {error}", file=sys.stderr)
        sys.exit(1)
