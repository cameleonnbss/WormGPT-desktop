# WormGPT — Desktop

A local, uncensored, offline AI desktop app for Windows. One folder, no
installation, no account, no cloud. Everything runs on your machine.

**Current version: v1.9** — see section 10 for the changelog.

---

## 1. What this app is

WormGPT runs **large language models locally** on your own computer, wrapped
in a dark/red chat interface (DarkGPT-style WebView2 UI). It ships with a
curated library of **15 uncensored open-source tiers** — downloaded once, then
used fully offline — plus:

- a **vision** tier that reads images you attach,
- a **code** tier for developers,
- **reasoning** tiers that show their thinking step by step,
- a **Dolphin** family,
- a **text-to-image** generator (stable-diffusion.cpp, bundled, offline),
- optional **cloud models** through your own OpenAI/Anthropic-compatible API key.

**Nothing ever leaves your machine.** There is no telemetry, no log shipping
and no account in this build. The only network calls are the
ones you trigger: downloading a model, using web search, or chatting with an
API you configured yourself.

---

## 2. Quick start

No admin rights are needed at any point.

1. Launch `WormGPT.exe`.
2. First-run wizard: choose your **language**, enter **your name** and the
   **name of your AI**, pick a model tier recommended for your hardware, choose
   a personality preset.
3. Open the **Models** page and download a tier (from ~400 MB to ~36 GB — start
   with a light one; they run on any machine). A red progress bar shows the
   speed; the model activates itself when the download completes.
4. Chat. Vision, image generation, web search, reasoning, the local API server
   and local command execution are all one click away.

---

## 3. Repository layout

```
main.py                 — entry point (WebView2 app)
WormGPT.spec            — PyInstaller spec (single-file exe)
build.bat               — one-click Windows build
requirements.txt        — Python dependencies
assets/                 — icons, logos, fonts, bundled SD engine
  sdengine/             — stable-diffusion.cpp (shipped next to the exe)
wormgpt/
  __init__.py           — version + resource paths
  config.py             — config schema, presets, defaults, factory reset
  core.py               — controller: engine, chat, downloads, tools
  engine.py             — llama.cpp wrapper (load, stream, reasoning split)
  models.py             — model catalog + parallel segmented downloader
  imagegen.py           — local text-to-image (stable-diffusion.cpp)
  server.py             — OpenAI/Anthropic-compatible local API server
  runner.py             — local command execution (agent mode)
  filesys.py            — file read/write/edit/glob/grep tools for the agent
  osint.py              — passive OSINT toolkit (public sources only)
  osint.py              — passive OSINT toolkit (public sources only)
  search.py             — web search for the model
  remote.py             — OpenAI / Anthropic / custom API providers
  systeminfo.py         — hardware detection + recommended settings
  stats.py              — local performance statistics
  discordbot.py         — optional Discord bot (your own token)
  i18n.py               — EN / FR / ES / DE strings
  theme.py              — app constants
  ui_web/
    bridge.py           — Python ⇄ WebView API
    static/             — HTML / CSS / JS interface
tools/                  — dev scripts (selftest, asset generation, probes)
```

---

## 4. Build from source

Requirements: Windows 10/11 64-bit, Python 3.12, and (for the first build)
internet access to fetch the llama-cpp-python wheel.

```bat
build.bat
```

Or manually:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.venv\Scripts\python tools\make_assets.py
.venv\Scripts\python -m PyInstaller --noconfirm WormGPT.spec
```

The result is `dist\WormGPT.exe` (single file, no console). Keep the `assets\`
folder next to it — it holds the fonts, logos and the bundled image engine.

Run the self-tests before shipping anything:

```bat
.venv\Scripts\python tools\selftest.py
```

---

## 5. The model library

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

Downloads use **16 parallel ranged streams** with per-segment resume: killing
the app mid-download and restarting picks up where it left off. Every file's
size is verified before it is installed.

---

## 6. Features

- **Chat** — streaming markdown, code blocks with copy buttons, per-conversation
  history archived locally, delete any conversation.
- **Reasoning** — always available; the thinking block streams separately.
- **Vision** — attach images to a vision tier.
- **Image generation** — local stable-diffusion.cpp (bundled) or your own
  Stable Diffusion WebUI; optional negative prompt, steps and CFG.
- **Web search** — DuckDuckGo / Wikipedia results fed back into the model.
- **Agent mode (Local Commands)** — the model can read, write and edit files,
  list/glob/grep folders, run shell commands and do passive OSINT, chaining
  tools until the task is done. "Ask" mode shows every command for approval;
  "Auto" runs without asking. Off by default.
- **Local API server** — OpenAI- and Anthropic-compatible on `127.0.0.1`.
- **Remote APIs** — OpenAI, Anthropic, xKiro or any compatible endpoint; their
  models appear in the same list as local ones.
- **Personalisation** — accent colour, animated particles, liquid-glass blur,
  and four UI languages (EN / FR / ES / DE), switched instantly.
- **Factory reset** — wipes all settings and restarts the wizard.

---

## 7. Where things are stored

| What | Where |
|------|-------|
| Config | `%APPDATA%\WormGPT\config.json` |
| Conversations | `%APPDATA%\WormGPT\history\` |
| Attached images | `%APPDATA%\WormGPT\images\` |
| Models | `%APPDATA%\WormGPT\models\` |
| Debug log | `%APPDATA%\WormGPT\debug.log` |

Delete that folder to start completely fresh (or use the in-app factory reset).

---

## 8. Privacy

This build **does not send anything anywhere by default**. Chat messages,
attachments, generated images and performance statistics are handled entirely
on your machine. Network access only happens when you:

- download a model from Hugging Face,
- enable web search,
- enable an optional remote API and chat with it.

Check the code: there is no telemetry module, no remote logging endpoint and no
hard-coded token anywhere in this repository.

---

## 9. Troubleshooting

- **"Windows protected your PC"** — More info → Run anyway. The exe is not
  code-signed.
- **Model won't load** — re-download it from the Models page; an interrupted
  download leaves a `.part` file that is detected and re-fetched. The app never
  deletes a model automatically.
- **Image generation fails** — the `assets\sdengine` folder must sit next to
  the exe (it is included in the release zip, not inside the exe).
- **Everything is slow** — pick a lower tier; each card lists its RAM need.
- **WebView2 missing** — install the "Microsoft Edge WebView2 Runtime" (already
  present on any up-to-date Windows 10/11).

---

## 10. Changelog (recent)

- **v1.10.0** — the setup wizard no longer shows the liability notice and its
  accept checkbox: the first screen is language only and **Continue** is live
  immediately.
- **v1.9.0** — private v1.9 release of WormGPT-desktop.
- **v1.19.0** — clicking a free cloud model card now routes the chat correctly
  (both remote sources are checked); "no model installed" fixed for API-only use.
- **v1.18.0** — chat auto-routes to your API when no local model is installed;
  agent mode offered in setup; language switches instantly; API key auto-saves
  on paste; cloud models labelled *Censored*.
- **v1.17.0** — white-on-accent text fixed; xKiro free cloud models added at the
  bottom of the list (hidden automatically when the API stops answering).
- **v1.16.0** — factory reset fixed (it restored the old config before wiping);
  the wizard now reliably reappears after a reset.
- **v1.15.0** — setup wizard language selector actually works; English is the
  default base language.
- **v1.14.0** — downloads are now 16-stream parallel (measured ~5× faster) with
  per-segment resume.
- **v1.13.0** — accent colour now drives the whole UI including particles;
  theme customisation no longer leaves stale red elements.

---

## 11. Français (résumé)

**WormGPT Desktop** est une application Windows qui fait tourner des **modèles
d'IA en local**, hors ligne, sans compte ni cloud, avec une interface sombre
rouge. Elle inclut 15 paliers de modèles non censurés, la lecture d'images, la
génération d'images (stable-diffusion.cpp embarqué), la recherche web, le
raisonnement, un serveur API local compatible OpenAI/Anthropic, un mode agent
qui exécute des commandes locales, et 4 langues d'interface.

**Aucune donnée ne quitte votre machine** : pas de télémétrie, pas de jeton
caché dans le code. Le réseau ne sert qu'au téléchargement des modèles, à la
recherche web et aux API que vous configurez vous-même.

**Démarrage** : lancer `WormGPT.exe`, suivre l'assistant (langue, votre nom,
nom de l'IA, modèle), puis télécharger un modèle dans l'onglet *Modèles* et
discuter. Aucun droit administrateur requis.

**Compilation** : `build.bat` (Python 3.12 + `requirements.txt`), puis
`.venv\Scripts\python tools\selftest.py`. Le résultat est `dist\WormGPT.exe` —
gardez le dossier `assets\` à côté.

**Où tout est stocké** : `%APPDATA%\WormGPT\` (config, conversations, images,
modèles, journal de debug).
