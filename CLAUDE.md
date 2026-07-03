# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PoE Price Check — a Windows-only overlay tool for Path of Exile 2. It screenshots the screen, OCRs item names with the built-in Windows OCR, matches them against poe.ninja prices, and draws the prices next to each item in a transparent click-through overlay. It is a Python re-implementation (feature-by-feature) of PoeAncientsPriceHelper.

All comments, docstrings, UI strings, and docs are in **Thai** — keep that convention when editing.

## Commands

```bash
py run.py                                  # run the full overlay app
py run.py --selftest                       # verify OCR works (must print "SELFTEST OK")
py -m unittest discover -s tests -v        # run all tests (offline: no network, no screen)
py -m unittest tests.test_matcher -v       # run a single test module
py -m poe_price "Runes of Aldur" -s "Divine Orb"   # CLI price lookup (no overlay)
py -m poe_price.scan "Runes of Aldur"      # capture screen -> OCR -> prices in terminal
```

Build (.exe): double-click `build.bat` (onefile) or `build-onedir.bat` (onedir + zip + SHA256 — flagged far less by antivirus). Requires Python 3.13 on Windows 10/11.

Release: bump `__version__` in `poe_price/__init__.py`, update `.github/whats-new.md` (this version's changelog section, replacing the previous one), commit, then push a `v*` tag — `.github/workflows/release.yml` tests, builds (onedir), zips, attests provenance, and publishes the GitHub Release using `.github/release-template.md` as the body. If PyInstaller flags change, update BOTH `build-onedir.bat` and the workflow.

## Hard build constraints

- Build from `run.py`, **not** `poe_price/app.py` — building from app.py breaks relative imports.
- `--collect-all winrt` is mandatory or OCR silently breaks in the .exe.
- `--windowed` builds log to `%LOCALAPPDATA%\PoePriceHelper\log.txt` (config JSON lives there too).

## Architecture

Two strictly separated layers:

1. **Price core** (`models.py`, `normalizer.py`, `client.py`, `matcher.py`, `repository.py`) — **zero dependencies**, pure stdlib. Fetches 14 categories from the poe.ninja PoE2 exchange API, normalizes names, fuzzy-matches OCR output. `PriceRepository` is the public entry (cache + 30-min auto-refresh + `get`/`match`). Keep this layer dependency-free.
2. **Windows layer** — screen capture via raw ctypes/GDI (`capture.py`), OCR via the official Microsoft `winrt-*` bindings (`ocr/`, pluggable engine behind `ocr/base.py`), overlay via tkinter + ctypes window styles (`overlay.py`), global hotkeys via `RegisterHotKey` (`hotkeys.py`). `scan.py` chains capture → OCR → match. `app.py` wires everything.

The only third-party deps in the whole project are the `winrt-*` OCR bindings.

### Rules that cross files (easy to break)

- **Threading:** tkinter lives on the main thread ONLY. Hotkey/worker threads communicate back exclusively through a `queue.Queue` that Tk polls with `root.after`. Never touch Tk objects from another thread.
- **DPI:** `set_dpi_aware()` must be called **before** creating Tk (done in `App.__init__`), otherwise capture/overlay coordinates diverge on scaled displays.
- **Overlay window styles:** `WS_EX_TRANSPARENT` (click-through) + `WS_EX_NOACTIVATE` (never steals focus from the game) are load-bearing safety properties documented in SECURITY.md — don't remove them.
- **Matching order:** gem (type+level pinned) → exact → prefix (≥10 chars) → fuzzy Levenshtein (>0.84), plus OCR digit-confusion fixes (1↔l/I) in `parse_quantity`. Tests in `tests/` encode this behavior.

### Security posture (from SECURITY.md — preserve it)

The program only screenshots, OCRs, and talks HTTPS to poe.ninja (the single external URL, in `client.py`). It must never read/write game memory, inject/hook, send input to the game, sniff packets, add telemetry, or download-and-execute code. New features must stay inside "read-only screen overlay".

## Tests

`unittest` (stdlib, no pytest). Tests are offline by design — no network calls, no screen capture; API responses are faked. New tests must follow this.
