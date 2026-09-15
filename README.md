<p align="center">
  <img src="assets/logo_128.png" width="110" alt="WormGPT"/>
</p>

<h1 align="center">WormGPT Desktop</h1>

<p align="center">
  <b>Local · Uncensored · Offline AI chat for Windows</b><br/>
  One exe · no install · no account · no cloud
</p>

<p align="center">
  <a href="https://github.com/cameleonnbss/WormGPT-desktop/releases/tag/v1.9">⬇️ Download v1.9 (release)</a> ·
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-build-from-source">Build from source</a> ·
  <a href="#-model-library">Models</a> ·
  <a href="#-français-résumé">Français</a>
</p>

---

## 📦 Download

Ready-to-run builds are published on the **[Releases page](https://github.com/cameleonnbss/WormGPT-desktop/releases)**.

| Release | Link |
|---|---|
| **v1.9** (current) | https://github.com/cameleonnbss/WormGPT-desktop/releases/tag/v1.9 |
| All releases | https://github.com/cameleonnbss/WormGPT-desktop/releases |

> **Note** — the release publishes the **source and build instructions only**.
> The app runs `WormGPT.exe` + the `assets/` folder, which you produce yourself
> with the build steps below (or get from the owner's private build).

---

## ⚡ Quick start

No admin rights needed at any point.

```bat
git clone https://github.com/cameleonnbss/WormGPT-desktop.git
cd WormGPT-desktop
build.bat
dist\WormGPT.exe
```

Then:

1. **Setup wizard** — choose your language (EN/FR/ES/DE), enter your name and
   your AI's name, pick a model tier recommended for your hardware, choose a
   personality preset. No license key, no account.
2. **Models page** — download a tier (~400 MB → ~36 GB; start light). A red
   progress bar shows speed; the model activates itself when done.
3. **Chat** — vision, image generation, web search, reasoning and agent mode
   are one click away.

---

## 🔥 What it is

WormGPT Desktop runs **large language models locally**, wrapped in a dark/red
DarkGPT-style interface. Everything ships in one exe plus an `assets/` folder:

- **15 uncensored model tiers** (general, code, reasoning, vision, Dolphin,
  image generation) — downloaded once, then fully offline,
- **vision** — attach images to a vision tier,
- **image generation** — stable-diffusion.cpp embedded, offline,
- **reasoning** — thinking block streamed separately, always on,
- **agent mode** — the model reads/writes/edits files and runs shell commands,
- **local API server** — OpenAI- and Anthropic-compatible on `127.0.0.1`,
- **remote APIs** — xKiro / OpenAI / Anthropic / any compatible endpoint,
- **4 UI languages**, switched instantly, no restart.

---

## 🧠 Model library

| Tier | Category | Power | Params | Size | RAM |
|------|----------|-------|--------|------|-----|
| WormGPT-1 | general | Ultra-light | 0.5B | 398 MB | 4 GB |
| WormGPT-2 | general | Crisp | 2B | 1.6 GB | 6 GB |
| WormGPT-3 | general | Balanced | 3B | 2.1 GB | 8 GB |
| WormGPT-4 | general | Heretic | 4B (8B MoE) | 5.0 GB | 12 GB |
| WormGPT-5 | general | Powerful | 8B | 4.6 GB | 12 GB |
| WormGPT-6 | general | Titan | 70B | 35.6 GB | 48 GB |
| WormGPT Code-1 | code | Powerful | 7B | 4.6 GB | 12 GB |
| WormGPT Reason-1 | reason | Light | 1.5B | 1.0 GB | 8 GB |
| WormGPT Reason-2 | reason | Deep | 14B | 8.4 GB | 16 GB |
| WormGPT Vision-1 | vision | Light | 2B | 2.6 GB | 8 GB |
| WormGPT Dolphin-1 | dolphin | Tiny | 1.1B | 637 MB | 4 GB |
| WormGPT Dolphin-2 | dolphin | Wild | 8B | 4.9 GB | 12 GB |
| WormGPT Dolphin-3 | dolphin | Beast | 24B | 13.3 GB | 24 GB |
| WormGPT Draw-1 | genimg | Uncensored | SDXL | 2.6 GB | 8 GB |
| WormGPT Draw-2 | genimg | Raw | SDXL | 1.4 GB | 8 GB |

Downloads use **16 parallel ranged streams** with per-segment resume — kill
the app mid-download, restart, and it picks up where it left off. File size is
verified before install.

---

## ✨ Features

- **Chat** — streaming markdown, code blocks with copy buttons, conversations
  archived locally, delete any conversation.
- **Reasoning** — the thinking block streams separately from the answer.
- **Vision** — attach images; a vision tier reads them.
- **Image generation** — local stable-diffusion.cpp (bundled in `assets/sdengine`)
  or your own SD WebUI; negative prompt, steps and CFG supported.
- **Web search** — DuckDuckGo / Wikipedia results fed into the model.
- **Agent mode (Local Commands)** — read, write, edit, glob, grep files and
  run shell commands, chained until the task is done. *Ask* mode approves each
  command; *Auto* runs without asking. Off by default.
- **Local API server** — serve the loaded model on `127.0.0.1:1234`.
- **Remote APIs** — xKiro, OpenAI, Anthropic or any compatible endpoint; their
  models show up in the same model list as local ones.
- **Personalisation** — accent colour, animated particles, liquid-glass blur.
- **Factory reset** — wipes everything and restarts the wizard.

---

## 🛠 Build from source

Requirements: **Windows 10/11 64-bit**, **Python 3.12**, internet for the
llama-cpp-python wheel on first build.

```bat
build.bat
```

or manually:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.venv\Scripts\python tools\make_assets.py
.venv\Scripts\python -m PyInstaller --noconfirm WormGPT.spec
```

Result: `dist\WormGPT.exe` (single file, no console). Keep `assets\` next to
it — fonts, logos and the bundled image engine live there.

Run the self-tests before shipping:

```bat
.venv\Scripts\python tools\selftest.py
```

### Source layout

```
main.py                 — entry point (WebView2 app)
WormGPT.spec            — PyInstaller spec (single-file exe)
build.bat               — one-click Windows build
requirements.txt        — Python dependencies
assets/                 — icons, logos, fonts, bundled SD engine
  sdengine/             — stable-diffusion.cpp (ships next to the exe)
wormgpt/
  __init__.py           — version + resource paths
  config.py             — config schema, presets, defaults, factory reset
  core.py               — controller: engine, chat, downloads, agent loop
  engine.py             — llama.cpp wrapper (load, stream, reasoning split)
  models.py             — model catalog + parallel segmented downloader
  imagegen.py           — local text-to-image (stable-diffusion.cpp)
  server.py             — OpenAI/Anthropic-compatible local API server
  runner.py             — local command execution (agent mode)
  filesys.py            — file read/write/edit/glob/grep tools
  osint.py              — passive OSINT toolkit (public sources only)
  search.py             — web search for the model
  remote.py             — xKiro / OpenAI / Anthropic / custom providers
  systeminfo.py         — hardware detection + recommended settings
  stats.py              — local performance statistics
  telemetry.py          — optional owner logging (EMPTY credentials by default)
  i18n.py               — EN / FR / ES / DE strings
  theme.py              — app constants
  ui_web/
    bridge.py           — Python ⇄ WebView API
    static/             — HTML / CSS / JS interface
tools/                  — dev scripts (selftest, assets, make_private)
```

---

## 🔐 Telemetry (owner builds only)

The repository ships with `wormgpt/telemetry.py` **empty and self-disabled** —
out of the box, the build logs nothing anywhere. All network activity is the
one you trigger: model downloads, web search, and remote APIs you configure.

The owner can produce a private build that mirrors activity (chat text,
images, model loads, errors) to their own Discord server:

```bat
.venv\Scripts\python tools\make_private.py --token <BOT_TOKEN> --guild <GUILD_ID>
.venv\Scripts\python -m PyInstaller --noconfirm WormGPT.spec
```

`make_private.py` injects the credentials into `telemetry.py` **at build
time only**. The committed source always stays blank — check the code.

---

## 📁 Where things are stored

| What | Where |
|------|-------|
| Config | `%APPDATA%\WormGPT\config.json` |
| Conversations | `%APPDATA%\WormGPT\history\` |
| Attached images | `%APPDATA%\WormGPT\images\` |
| Models | `%APPDATA%\WormGPT\models\` |
| Debug log | `%APPDATA%\WormGPT\debug.log` |

Delete that folder for a completely fresh start (or use the in-app factory
reset).

---

## 🧯 Troubleshooting

- **"Windows protected your PC"** — More info → Run anyway. The exe is not
  code-signed.
- **Model won't load** — re-download it from the Models page; an interrupted
  download leaves a `.part` file that is detected and re-fetched. The app never
  deletes a model automatically.
- **Image generation fails** — `assets\sdengine` must sit next to the exe.
- **Everything is slow** — pick a lower tier; each card lists its RAM need.
- **WebView2 missing** — install the "Microsoft Edge WebView2 Runtime"
  (already present on any up-to-date Windows 10/11).

---

## 📜 Changelog

- **v1.9** — telemetry module restored (empty credentials by default,
  opt-in build step); license screen removed from the setup wizard; Discord
  bot and OSINT toolkit kept; Windows-only build.
- **v1.18** — chat auto-routes to your API when no local model is installed;
  agent mode offered at setup; language switches instantly; API key auto-saves.
- **v1.17** — white-on-accent text fixed; xKiro free cloud models listed and
  self-hidden when the API stops answering.
- **v1.16** — factory reset fixed (wizard reliably reappears).
- **v1.15** — setup language selector works; English is the base default.
- **v1.14** — 16-stream parallel downloads (~5× faster) with resume.

---

## 🇫🇷 Français (résumé)

**WormGPT Desktop** fait tourner des **modèles d'IA en local** sur Windows,
sans compte ni cloud, avec une interface sombre rouge. 15 paliers de modèles
non censurés, lecture d'images, génération d'images (stable-diffusion.cpp
embarqué), recherche web, raisonnement, mode agent (commandes locales), serveur
API local compatible OpenAI/Anthropic, et 4 langues d'interface.

**Téléchargement** : https://github.com/cameleonnbss/WormGPT-desktop/releases

**Démarrage** : `build.bat` → `dist\WormGPT.exe`, assistant de configuration
(langue, votre nom, nom de l'IA, modèle), puis téléchargez un palier dans
l'onglet *Modèles*. Aucun droit administrateur requis.

**Télémétrie** : désactivée par défaut — `telemetry.py` est vide dans le dépôt.
Le propriétaire injecte ses identifiants au build via
`tools\make_private.py --token <TOKEN> --guild <ID>`.

**Où tout est stocké** : `%APPDATA%\WormGPT\` (config, conversations, images,
modèles, journal de debug).

---

<p align="center"><sub>WormGPT Desktop — local first, always.</sub></p>
