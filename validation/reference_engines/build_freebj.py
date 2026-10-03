"""Build a clean pinned FreeBJ checkout with an already installed Rust toolchain."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.references import _checkout_provenance, _pin, _sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--cargo-home")
    parser.add_argument("--rustup-home")
    parser.add_argument("--gcc-bin")
    args = parser.parse_args()
    checkout, target = Path(args.checkout).resolve(), Path(args.target_dir).resolve()
    pin = _pin("kevin-lesenechal/freebj")
    provenance = _checkout_provenance(checkout, pin)
    environment = dict(os.environ)
    prefixes = []
    if args.cargo_home:
        environment["CARGO_HOME"] = str(Path(args.cargo_home).resolve())
        prefixes.append(str(Path(args.cargo_home).resolve() / "bin"))
    if args.rustup_home:
        environment["RUSTUP_HOME"] = str(Path(args.rustup_home).resolve())
    if args.gcc_bin:
        prefixes.append(str(Path(args.gcc_bin).resolve()))
    environment["PATH"] = os.pathsep.join([*prefixes, environment.get("PATH", "")])
    cargo = shutil.which("cargo", path=environment["PATH"])
    if not cargo:
        raise FileNotFoundError("cargo is not present in the supplied toolchain")
    rustc = shutil.which("rustc", path=environment["PATH"])
    flags = []
    if os.name == "nt" and args.rustup_home:
        root_result = subprocess.run([rustc, "--print", "sysroot"], env=environment, capture_output=True, text=True, shell=False)
        bundled = Path(root_result.stdout.strip()) / "lib" / "rustlib" / "x86_64-pc-windows-gnu" / "bin" / "self-contained" / "x86_64-w64-mingw32-gcc.exe"
        if bundled.is_file():
            # GNU Rust's bundled libraries and linker must agree. An external
            # w64devkit GCC lacks libgcc_eh and must not override that linker.
            environment["CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER"] = str(bundled)
            flags.append("-Clink-self-contained=yes")
        if args.gcc_bin:
            dlltool = Path(args.gcc_bin).resolve() / "dlltool.exe"
            if dlltool.is_file():
                flags.append("-Cdlltool=" + str(dlltool))
        if flags:
            environment["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
    command = [cargo, "build", "--release", "--locked", "--target-dir", str(target)]
    result = subprocess.run(command, cwd=checkout, env=environment, capture_output=True, text=True, shell=False)
    receipt_path = Path(args.receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = receipt_path.with_suffix(".build.log")
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        print(result.stderr[-10000:])
        raise SystemExit(result.returncode)
    _checkout_provenance(checkout, pin)  # ensure no tracked source changed during build.
    binary = target / "release" / ("freebj.exe" if os.name == "nt" else "freebj")
    rust = subprocess.run([rustc, "--version"], env=environment, capture_output=True, text=True, shell=False)
    receipt = {"schema_version": 1, "status": "built", **provenance,
               "binary_path": str(binary), "binary_sha256": _sha256(binary), "command": command,
               "rustc": rust.stdout.strip(), "build_log": str(log_path.resolve()),
               "rust_flags": flags, "target_linker": environment.get("CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER"),
               "build_log_sha256": _sha256(log_path), "executed_at": datetime.now(timezone.utc).isoformat()}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
