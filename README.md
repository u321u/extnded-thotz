# Extnded Thotz

<img src="assets/logo.png" alt="Extnded Thotz logo" width="120" align="right" />

**Hold a key. Speak. Watch polished text appear wherever your cursor is.**

Extnded Thotz is a Windows voice-dictation app in the spirit of tools like Wispr Flow:
a system-wide push-to-talk hotkey records your voice, transcribes it **locally and
offline** with Whisper, cleans it up (filler words, punctuation, capitalization,
voice commands), and inserts the result into whatever app has focus — Notepad,
your browser, Slack, your IDE, anywhere.

*Independent implementation — no third-party code, assets, or branding. The goat is ours.*

## Quick start

```bash
pip install -r requirements.txt
python -m extnded_thotz
```

The goat icon appears in your system tray. Then, in any app:

1. **Hold Right Ctrl** and speak.
2. A small **"● Listening"** pill appears at the bottom of the screen.
3. **Release** — the pill switches to "… Transcribing", and a moment later your
   words are pasted at the cursor, cleaned up.

Press **ESC while recording** to cancel. Taps shorter than 0.25 s are ignored.

The first dictation downloads the Whisper `base` model (~145 MB, one time).
Start the app before you need it — the model preloads in the background.

## Voice commands

| Say | Get |
|---|---|
| "new line" | line break |
| "new paragraph" | blank line |

Filler words ("um", "uh", "hmm"…) are removed automatically. Both behaviors can
be turned off in Settings.

## Settings

Tray icon → **Settings…** (or `python -m extnded_thotz.settings_ui`). Changes
apply to the running app within ~2 seconds — no restart needed.

- **Dictation key / mode** — `right ctrl` hold-to-talk by default; or pick F9 etc. with `toggle` (tap to start, tap to stop).
- **Backend** — `auto` uses local Whisper unless an OpenAI API key is configured; force `local` or `openai`.
- **Local model size** — `tiny`/`base` are fast; `small` is noticeably more accurate on a decent CPU; `large-v3` is best but slow without a GPU.
- **AI polish** — optional second pass through `gpt-4o-mini` for smarter punctuation and false-start removal. Needs an API key; fails soft (you always get the local cleanup result).
- **Insert method** — `paste` (default, instant) or `type` (per-character, for apps that block paste). Your clipboard is restored ~0.6 s after pasting.

Config lives at `%APPDATA%\ExtndedThotz\config.json`. Dictation history:
`%APPDATA%\ExtndedThotz\history.jsonl`. Log: `%APPDATA%\ExtndedThotz\app.log`.

## Privacy

With the default local backend, **audio never leaves your machine** — recording,
transcription, and cleanup all happen on-device. Only if you configure an OpenAI
key *and* enable the cloud backend or AI polish is text/audio sent to OpenAI.

## Start with Windows

`Win+R` → `shell:startup` → create a shortcut with target:

```
pythonw -m extnded_thotz
```

(`pythonw` runs it without a console window.)

## Development

```bash
pip install -r requirements-dev.txt
python scripts/make_fixture.py   # generates a TTS voice fixture (SAPI)
python -m pytest -q              # full suite, incl. offline STT end-to-end
python -m extnded_thotz --smoke 4     # 4-second launch self-test
python -m extnded_thotz --once file.wav   # transcribe a WAV from the CLI
```

The implementation plan (architecture, module specs, roadmap) is in
`docs/superpowers/plans/2026-07-02-extnded-thotz-mvp.md`.

### Manual test checklist (needs a real mic + voice)

1. Run `python -m extnded_thotz`; goat icon appears in tray.
2. Focus Notepad, hold Right Ctrl, say "hello world this is a test", release → text appears; pill shows Listening → Transcribing → hides.
3. Say "first item new line second item" → two lines.
4. Hold the key, press ESC → "Cancelled" pill, nothing inserted.
5. Tap the key for <0.25 s → nothing happens (accidental-tap guard).
6. Copy some text, dictate somewhere, then paste → your original clipboard is back.
7. Settings: switch to F9 + toggle mode, Save → within 2 s, F9 tap starts/stops dictation.
8. Tray → Quit → icon disappears, process exits, hotkey stops reacting.

## Packaging (optional)

```bash
pip install pyinstaller
pyinstaller --noconsole --name ExtndedThotz --icon assets/logo.png ^
  --add-data "assets;assets" --collect-all faster_whisper -m extnded_thotz
```

## Known limitations

- Dictating into apps running **as administrator** requires running Extnded Thotz elevated too (Windows blocks cross-elevation input).
- `base` model accuracy is mid — bump to `small` if you have the CPU headroom.
- Saying the literal words "new line" inserts a line break when voice commands are on (that's the feature; toggle it off if you write about newlines a lot).

## Roadmap

Streaming partial transcripts · hands-free voice-activity mode · personal
dictionary (name/jargon biasing) · per-app tone profiles · command mode
("delete that") · one-file installer · auto-update.
