# Extnded Thotz — ExtndedThotz
> Moments lost in thought, made into text.

Extnded Thotz is a free Windows voice dictation app: hold a hotkey, speak, and
clean, punctuated text lands at your cursor. Transcription runs locally with
Whisper — audio never leaves the machine.

Extended thoughts. Zero typing. That's the whole idea.

## Site map
- `/` — homepage (hero, live demo, features, comparison)
- `/download` — portable .exe + .zip, SHA-256 checksums
- `/faq` — privacy, hotkeys, compatibility, SmartScreen

## Stack
- Static HTML + CSS + vanilla JS (digital rain canvas, live dictation demo)
- Served by Vercel; Flask app (`app.py`) provides the local/dev routes
- Fonts: Space Grotesk, Fraunces, IBM Plex Mono (self-hosted woff2)

## Dev
```bash
python -m app           # requires: pip install -r requirements.txt
vercel --prod --yes     # deploy
```

## Rules for editing this site
- Every class used in HTML must exist in styles.css — run the parity check
- Keep the header/footer byte-identical across all pages
- Never link to removed routes (/pricing is dead, don't resurrect it)
- The goat logo (`assets/logo.png`) is the brand mark; keep it in header + footer
- Matrix edition is the one theme: phosphor green `#35e07a` on near-black `#020604`
