from pathlib import Path
import re

def read(p):
    return Path(p).read_text(encoding="utf-8")

def write(p, s):
    Path(p).write_text(s, encoding="utf-8")

# ---------------- index.html ----------------
p = Path("index.html")
s = read(p)

s = s.replace('<meta name="theme-color" content="#050403" />',
              '<meta name="theme-color" content="#0a0a0b" />')

for emoji in ['🔒', '⚡', '🎯', '🖥️', '📋', '🚀', '👁', '💬', '📌']:
    s = s.replace(f'<div class="feature-icon" aria-hidden="true">{emoji}</div>',
                  '<div class="feature-icon" aria-hidden="true"></div>')

s = re.sub(r'<section class="section shell" id="testimonials"[^>]*>.*?</section>', '', s, flags=re.S)

s = s.replace('Premium features', 'Features')
s = s.replace('Everything you need to dictate with confidence', 'A small set of things it actually does well')
s = s.replace('Built like a professional tool. Polished, fast, and reliable.', '')
s = s.replace('Dictate like a pro. Save hours every week.',
              'Free Windows dictation. Pick it up now.')
s = s.replace('Type less. Think more. Get your words down instantly with private, local dictation.',
              'Free voice dictation for Windows. Hold Ctrl + Windows, speak, release. No cloud by default.')
s = s.replace('Download for Windows - Free to try', 'Download for Windows — free')
s = s.replace('It feels polished, premium, and actually useful.', 'It is useful and fast.')
s = s.replace('Loved by power users', '')

s = s.replace(
    '<li>Local Whisper transcription</li>\n            <li>Works in any Windows app</li>\n            <li>Matrix-style listening overlay</li>\n            <li>Free download · $29 optional</li>',
    '<li>Free to download and use</li>\n            <li>Local Whisper transcription</li>\n            <li>Works in any Windows app</li>\n            <li>Optional $29 Pro license</li>',
)

write(p, s)
print("index.html cleaned")

# ---------------- download.html ----------------
p = Path("download.html")
s = read(p)

s = s.replace('<meta name="theme-color" content="#050403" />',
              '<meta name="theme-color" content="#0a0a0b" />')
s = s.replace('<title>Download Extnded Thotz for Windows | Free to try</title>',
              '<title>Download Extnded Thotz for Windows — free</title>')
s = s.replace(
    '<meta name="description"\n      content="Download Extnded Thotz for Windows — portable .exe, local Whisper transcription, no Python required. Free to try, $29 one-time."\n    />',
    '<meta name="description"\n      content="Free Windows voice dictation app. Portable .exe, local Whisper transcription, no Python required."\n    />',
)
s = s.replace('content="Portable Windows build — one executable, local transcription, no cloud required."',
              'content="Free Windows voice dictation. Hold a hotkey, speak, get text. Local Whisper transcription, no cloud by default."')
s = s.replace('content="Extnded Thotz — voice dictation for Windows"',
              'content="Extnded Thotz — free Windows voice dictation"')
s = s.replace(
    'The portable Windows build — one executable, no Python setup. Published SHA-256 checksums included.',
    'Free Windows voice dictation. Hold a hotkey, speak, get text. Local Whisper transcription, no cloud by default.',
)
s = s.replace(
    "Start dictating in seconds. Portable executable, local Whisper transcription, no Python setup. Free to try.\n          Upgrade to Pro for $29 one-time when you're ready.",
    'Free Windows dictation app. Hold a hotkey, speak, release, and your words appear at the cursor. Transcription is local by default and your audio never leaves your machine.',
)
s = s.replace('<h3>Get Extnded Thotz</h3>',
              '<h3>Get Extnded Thotz — free</h3>')
s = s.replace('<p>Windows 10 or 11 · Portable · ~22 MB</p>',
              '<p>Windows 10 or 11 · Portable · ~22 MB · Free to use</p>')
s = s.replace('<li>Free to try. $29 one-time for Pro</li>',
              '<li>Free to download and use</li>')
s = s.replace('Ready in under a minute.</h2>',
              'Free Windows dictation. Pick it up now.</h2>')
s = s.replace(
    'Run the executable, pin it to your tray, and dictate into any app with\n          <code>Ctrl + Windows</code>.',
    'Free Windows voice dictation. Hold Ctrl + Windows, speak, release. No cloud by default.',
)
s = s.replace(
    '<a class="button primary large" href="/downloads/ExtndedThotz.exe" download>Download .exe (22 MB)</a>',
    '<a class="button primary large" href="/downloads/ExtndedThotz.exe" download>Download for Windows — free</a>',
)

write(p, s)
print("download.html cleaned")

# ---------------- pricing.html ----------------
p = Path("pricing.html")
s = read(p)

s = s.replace('<meta name="theme-color" content="#050403" />',
              '<meta name="theme-color" content="#0a0a0b" />')
s = s.replace('<title>Pricing | Extnded Thotz — $29 one-time</title>',
              '<title>Pricing — free to use, $29 optional Pro</title>')
s = s.replace(
    '<meta name="description"\n      content="Extnded Thotz Pro is a $29 one-time purchase — the Windows app, local Whisper dictation, and all current updates. No subscription."\n    />',
    '<meta name="description"\n      content="Free Windows voice dictation app. Optional $29 Pro license for a one-time license and updates."\n    />',
)
s = s.replace(
    'content="One license, one app, one download. $29 one-time for Extnded Thotz Pro with all current updates."',
    'content="Free Windows voice dictation. Optional one-time $29 license if you want to support Pro."',
)
s = s.replace('Simple one-time purchase.</h1>',
              'Free to use. $29 optional.</h1>')
s = s.replace(
    'Luxury software should be simple to own. One license, one app, one download —\n          and no subscription watching the clock.',
    'Extnded Thotz is free to download and use. Pay $29 once if you want a Pro license and updates. No subscription, no recurring fees, no surprises.',
)
s = s.replace('<h3>Extnded Thotz Pro</h3>',
              '<h3>Extnded Thotz — free, with optional Pro</h3>')
s = s.replace('One-time license for the Windows app and current updates.',
              'Free Windows voice dictation app. Optional $29 one-time Pro license if you want a license and updates.')
s = s.replace('<span class="price-terms">one-time · yours to keep</span>',
              '<span class="price-terms">optional one-time · yours to keep</span>')
s = s.replace('<li>All current updates included</li>',
              '<li>Optional $29 Pro license</li>')
s = s.replace(
    '<li>Custom hotkey, modes, and cleanup controls</li>\n          </ul>',
    '<li>Custom hotkey, modes, and cleanup controls</li>\n            <li>Optional $29 Pro license</li>\n          </ul>',
)
s = s.replace('<a class="button primary full" href="/download">Get Extnded Thotz</a>',
              '<a class="button primary full" href="/download">Go to download — free</a>')
s = s.replace(
    'You can start with the free build today, or\n            <a href="mailto:hello@scoutgoat.com?subject=Extnded%20Thotz%20license"\n              >email us to buy a license</a\n            >\n            now.',
    'You can start with the free build today, or\n            <a href="mailto:hello@scoutgoat.com?subject=Extnded%20Thotz%20license"\n              >email us for the optional Pro license</a\n            >\n            now.',
)
s = s.replace('<p class="eyebrow">Before you buy</p>',
              '<p class="eyebrow">Free app, optional Pro</p>')
s = s.replace('<h2>Fair questions, straight answers.</h2>',
              '<h2>Questions about the free app and optional Pro?</h2>')
s = s.replace('What do I get for $29?', 'How does the $29 Pro license work?')
s = s.replace(
    'A one-time license for the Extnded Thotz Windows app, including every\n              current update. There is no subscription and no renewal.',
    '$29 is an optional one-time license if you want to support Pro. The app itself is free to use, and the free version has no trial timer.',
)
s = s.replace('Can I try it first?', 'Is there a free version?')
s = s.replace(
    'Yes. The portable build on the download page runs without payment, so you\n              can dictate for a week before deciding.',
    'Yes. You can download and use Extnded Thotz for free. The app is a portable Windows executable — no installation, no Python setup, no payment required.',
)
s = s.replace('<a class="button primary" href="/download">Get the download</a>',
              '<a class="button primary" href="/download">Go to download — free</a>')
s = s.replace(
    '<a class="button secondary" href="mailto:hello@scoutgoat.com?subject=Extnded%20Thotz%20checkout"\n            >Connect checkout</a\n          >',
    '<a class="button secondary" href="mailto:hello@scoutgoat.com?subject=Extnded%20Thotz%20license"\n            >Get the optional Pro license</a\n          >',
)

write(p, s)
print("pricing.html cleaned")

# ---------------- faq.html ----------------
p = Path("faq.html")
s = read(p)

s = s.replace('<meta name="theme-color" content="#050403" />',
              '<meta name="theme-color" content="#0a0a0b" />')
s = s.replace('<title>FAQ | Extnded Thotz — Voice dictation for Windows</title>',
              '<title>FAQ — Free Windows voice dictation</title>')
s = s.replace(
    '<meta name="description"\n      content="Answers about Extnded Thotz: privacy and local Whisper, Windows support, the hotkey, the portable build, and how to buy."\n    />',
    '<meta name="description"\n      content="Free Windows voice dictation app: privacy, local Whisper, hotkeys, portable build, and optional $29 Pro license."\n    />',
)

s = s.replace('Questions serious buyers ask.</h1>',
              'Questions about Extnded Thotz</h1>')
s = s.replace(
    'Privacy, platforms, hotkeys, and licensing — the answers people want before\n          they install anything.',
    'Privacy, compatibility, setup, and licensing — straight answers about the free Windows dictation app.',
)
s = s.replace('<p class="eyebrow">FAQ</p>',
              '<p class="eyebrow">Free app</p>')

faq_map = [
    ("Does it send audio to the cloud?", "Is Extnded Thotz free?"),
    (
        "Not by default. Transcription runs on your machine with local Whisper, so\n              your audio never leaves your computer unless you enable the cloud backend or\n              AI polish.",
        "Yes. You can download and use Extnded Thotz for free. The app is a portable Windows executable — no installation, no Python setup, no payment required.",
    ),
    ("Do I need Python installed?", "How does the $29 Pro license work?"),
    (
        "No. The download is a portable Windows executable — nothing to install, no\n              dependencies to set up.",
        "$29 is an optional one-time license if you want to support Pro. The app itself is free to use, and the free version has no trial timer.",
    ),
    ("Which Windows versions are supported?", "Does it send audio to the cloud?"),
    (
        "Windows 10 and Windows 11. The build is Windows-first; there is no macOS or\n              Linux version yet.",
        "No. Transcription runs on your machine with local Whisper by default. Your audio never leaves your computer unless you explicitly enable a cloud backend or AI polish.",
    ),
    ("Can I change the hotkey?", "Do I need Python installed?"),
    (
        "Yes. The settings window lets you record any key or chord, then choose\n              hold-to-talk or toggle mode.",
        "No. The download is a portable Windows executable. Just download and run it — no dependencies, no install wizard.",
    ),
    ("Does it work in every app?", "Which Windows versions are supported?"),
    (
        "In any normal app — Notepad, your browser, Slack, your IDE. Dictating into\n              apps running as administrator requires running Extnded Thotz elevated too,\n              because Windows blocks input across privilege levels.",
        "Windows 10 and Windows 11. The app is optimized for modern Windows. There are no macOS or Linux builds yet.",
    ),
    ("How does licensing work?", "Can I change the hotkey?"),
    (
        "One-time $29 purchase covering the Windows app and all current updates. No\n              subscription.",
        "Yes. The settings window lets you record any key or chord, then choose hold-to-talk or toggle mode.",
    ),
]

for a, b in faq_map:
    s = s.replace(a, b)

write(p, s)
print("faq.html cleaned")
