# Changelog

## 1.0.6 — 2026-10-23

- Fixed dictation failing on Windows machines where the default input is a dead Sound Mapper / virtual endpoint. The recorder now skips mixer endpoints, tries real microphones (best host API first) before the OS default, and never retries an endpoint that hung inside its driver.
- A wedged audio driver no longer freezes quit: the window tears down first and the process exits instead of hanging after you close it.
- Removed the startup microphone probe that opened every endpoint before the first dictation and could leave the audio stack stuck.
- Windows download now points at the 1.0.6 build.

## 1.0.3 — 2026-10-22

- Windows releases are now built by the committed `ExtndedThotz-win.spec` in GitHub Actions and attached to a tagged commit, instead of being built by hand on one machine.
- The executable no longer bundles `duckdb`, `botocore`, `boto3`, `matplotlib` and `pytest`, which PyInstaller had been pulling in through optional import paths. The download drops from ~157 MB to ~100 MB.
- Each release ships `SHA256SUMS.txt` next to the executable, generated from the same artifact.
- The site's download redirect points at the 1.0.3 asset.

## 1.0.2 — 2026-10-22

- Fixed the Windows download. The published file was the on-dir build, which needed an `_internal` folder that was never uploaded, so it failed at startup with a missing `python314.dll`. It is now a self-contained one-file executable.
- The macOS build stays a separate universal2 zip.
