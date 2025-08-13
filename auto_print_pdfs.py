#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess
import shlex
from datetime import datetime

STATE_FILE = ".auto_print_state.json"
PDF_MAGIC = b"%PDF-"

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def warn(msg):
    log(f"WARNING: {msg}")

def err(msg):
    log(f"ERROR: {msg}")

def list_printers():
    printers = []
    default_printer = None
    try:
        out = subprocess.check_output(["lpstat", "-p"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "printer":
                printers.append(parts[1])
    except Exception as e:
        err(f"Could not list printers: {e}")

    try:
        d = subprocess.check_output(["lpstat", "-d"], text=True).strip()
        if ":" in d:
            default_printer = d.split(":", 1)[1].strip()
    except Exception:
        pass

    return printers, default_printer

def choose_printer(printers, default_printer):
    if not printers:
        err("No printers found. Please install a printer and try again.")
        sys.exit(1)
    log("Available printers:")
    for i, p in enumerate(printers, 1):
        tag = " (default)" if p == default_printer else ""
        print(f"{i}. {p}{tag}")
    while True:
        choice = input(f"Choose printer [1-{len(printers)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(printers):
            return printers[int(choice) - 1]
        warn("Invalid selection. Please enter a number from the list.")

def get_print_options():
    pages = input("Enter page ranges (e.g., 1-3,5,7) or press Enter for all pages: ").strip()
    while True:
        copies = input("Enter number of copies (default 1): ").strip()
        if not copies:
            copies = 1
            break
        if copies.isdigit() and int(copies) > 0:
            copies = int(copies)
            break
        warn("Invalid number of copies. Please enter a positive integer.")

    duplex_modes = ["one-sided", "two-sided-long-edge", "two-sided-short-edge"]
    print("Duplex options:")
    for i, mode in enumerate(duplex_modes, 1):
        print(f"{i}. {mode}")
    while True:
        duplex_choice = input("Choose duplex mode [1-3] or press Enter for default: ").strip()
        if not duplex_choice:
            duplex = None
            break
        if duplex_choice.isdigit() and 1 <= int(duplex_choice) <= len(duplex_modes):
            duplex = duplex_modes[int(duplex_choice) - 1]
            break
        warn("Invalid duplex choice. Please enter 1, 2, 3, or press Enter.")

    fit_input = input("Fit to page? (Y/N, default N): ").strip().lower()
    fit = fit_input == "y"

    media = input("Enter paper size (e.g., Letter, A4) or press Enter for default: ").strip() or None

    return pages, copies, duplex, fit, media

def is_pdf(path):
    if not path.lower().endswith(".pdf"):
        return False
    try:
        with open(path, "rb") as f:
            return f.read(5) == PDF_MAGIC
    except Exception:
        return False

def print_pdf(path, printer, pages, copies, duplex, fit, media):
    cmd = ["lp", "-d", printer]
    if copies and copies != 1:
        cmd += ["-n", str(copies)]
    if pages:
        cmd += ["-P", pages]
    if duplex:
        cmd += ["-o", f"sides={duplex}"]
    if fit:
        cmd += ["-o", "fit-to-page"]
    if media:
        cmd += ["-o", f"media={media}"]
    cmd.append(path)

    log("Printing: " + " ".join(shlex.quote(x) for x in cmd))
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        err(f"Printing failed with exit code {e.returncode}")
        return False
    except Exception as e:
        err(f"Unexpected printing error: {e}")
        return False

def watch_folder(folder, printer, pages, copies, duplex, fit, media):
    printed_files = {}
    log(f"Watching folder: {folder}")
    log("Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        log("Stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                if not is_pdf(path):
                    continue
                mtime = os.path.getmtime(path)
                if path not in printed_files or printed_files[path] < mtime:
                    if print_pdf(path, printer, pages, copies, duplex, fit, media):
                        printed_files[path] = mtime
            time.sleep(5)
        except Exception as e:
            warn(f"Error scanning folder: {e}")
            time.sleep(5)

if __name__ == "__main__":
    folder = os.path.dirname(os.path.abspath(__file__))
    printers, default_printer = list_printers()
    printer = choose_printer(printers, default_printer)
    pages, copies, duplex, fit, media = get_print_options()
    watch_folder(folder, printer, pages, copies, duplex, fit, media)
