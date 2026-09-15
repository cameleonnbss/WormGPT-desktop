"""Bridge between the web UI and the Core controller.

The HTML page calls `window.pywebview.api.<method>(...)`. Python pushes UI
events through `pull()` — the page polls it a few times per second, which
avoids all thread-safety issues of evaluate_js from worker threads.
"""

import base64
import datetime
import os
import queue
import threading

from .. import config as C
from .. import i18n as _
from .. import models as M
from .. import systeminfo as SI
from .. import theme as T
from ..core import Core


class Bridge:
    def __init__(self, cfg):
        self.cfg = cfg
        self._events = queue.Queue()
        # au premier lancement (pas encore configuré) on ne démarre AUCUN
        # modèle : _auto_start ne doit tourner qu'une fois configuré
        if not cfg.get("configured"):
            Core._auto_start = lambda self: None
        self.core = Core(cfg, self._events.put)
        # session télémétrie alignée sur la conversation ouverte au départ
        self.core._tel_sync()

    # -- event pump ---------------------------------------------------------

    def pull(self):
        batch = []
        while True:
            try:
                batch.append(self._events.get_nowait())
            except queue.Empty:
                break
        return batch

    # -- init ---------------------------------------------------------------

    def init(self):
        cfg = self.cfg
        return {
            "app_name": T.APP_NAME,
            "version": T.APP_VERSION,
            "lang": _.get_lang(),
            "strings": _.get_table(),
            "configured": bool(cfg.get("configured")),
            "ai_name": (cfg.get("ai_name") or "WormGPT"),
            "user_name": ((cfg.get("profile") or {}).get("name") or ""),
            "session_id": cfg.get("session_id", ""),
            "language": cfg.get("language", "en"),
            "presets": [{"key": k, "name": n, "text": t}
                        for k, n, t in C.localized_presets(_.get_lang())],
            "preset": cfg.get("preset", "Security Professional"),
            "system_prompt": cfg.get("system_prompt", ""),
            "recommended": SI.recommended_tier(),
            "settings": self.settings_state(),
        }

    def settings_state(self):
        cfg = self.cfg
        return {
            "ai_name": cfg.get("ai_name") or "WormGPT",
            "user_name": ((cfg.get("profile") or {}).get("name") or ""),
            "temperature": cfg["engine"].get("temperature", 0.7),
            "max_tokens": cfg["engine"].get("max_tokens", 1024),
            "image": dict(cfg.get("image", {})),
            "server": dict(cfg.get("server", {})),
            "tools": dict(cfg.get("tools", {})),
            "search": bool(cfg.get("search", {}).get("enabled")),
            "reasoning": bool(cfg.get("reasoning", {}).get("show", True)),
            "uncensored": bool(cfg.get("uncensored", {}).get("enabled", True)),
            "ui": dict(cfg.get("ui", {})),
            "providers": {k: dict(v or {}) for k, v
                          in (cfg.get("providers") or {}).items()},
            "remote": dict(cfg.get("remote", {})),
            "remote_active": self.core.remote_active(),
            "model": self.core.current_model_label(),
            "engine": {"state": self.core.engine_state,
                       "text": self.core.engine_status},
            "server_running": bool(self.core.server and self.core.server.running),
            "recommended": SI.recommended_tier(),
        }

    def active_tier_name(self):
        return self.core.active_tier_name()

    # -- wizard / profile ---------------------------------------------------

    def set_language(self, lang):
        """Changement de langue à chaud (sélecteur du wizard).

        Renvoie la table de chaînes de la langue choisie pour que l'interface
        se repeigne immédiatement pendant l'installation."""
        code = (lang or "en").strip() or "en"
        if code not in ("en", "fr", "es", "de"):
            code = "en"
        _.set_lang(code)
        self.cfg["language"] = code
        C.save(self.cfg)
        return {"ok": True, "language": code, "strings": _.get_table()}

    def finish_setup(self, payload):
        """payload: {language, user_name, ai_name, preset, tier}

        Au premier lancement RIEN n'est lancé : on mémorise seulement le
        modèle souhaité. Le téléchargement reste un clic explicite sur la
        page Modèles (pas de sélection/download automatiques)."""
        data = payload or {}
        lang = data.get("language") or "en"
        _.set_lang(lang)
        self.cfg["language"] = lang
        self.cfg["ai_name"] = (data.get("ai_name") or "WormGPT").strip() \
            or "WormGPT"
        user_name = (data.get("user_name") or "").strip()
        self.cfg.setdefault("profile", {})["name"] = user_name
        preset = data.get("preset") or "Security Professional"
        self.cfg["preset"] = preset
        self.cfg["system_prompt"] = C.preset_text(preset, lang)
        self.cfg["system_prompt_custom"] = False
        # mode agent (commandes locales) choisi au setup — même titre que
        # dans les réglages « Local Commands »
        tools = self.cfg.setdefault("tools", {})
        tools["enabled"] = bool(data.get("agent"))
        tools["mode"] = "auto" if data.get("agentMode") == "auto" else "ask"
        # modèle CHOISI dans le wizard = simple préférence ; rien n'est
        # téléchargé ni chargé automatiquement au premier lancement
        tier = data.get("tier") or SI.recommended_tier()
        self.cfg["model"]["tier"] = tier
        self.cfg["model"]["path"] = M.catalog_path(tier)
        # apparence choisie pendant la configuration (étape 3) : couleur
        # d'accent, particules, effet verre… appliqués dès le premier écran
        ui = data.get("ui") or {}
        if isinstance(ui, dict) and ui:
            cur_ui = dict(self.cfg.get("ui") or {})
            cur_ui.update({k: v for k, v in ui.items() if v is not None})
            self.cfg["ui"] = cur_ui
        # performance conseillée pour la machine (fenêtre de contexte/threads)
        eng = data.get("engine") or {}
        if isinstance(eng, dict) and eng:
            cur_eng = dict(self.cfg.get("engine") or {})
            for k in ("n_ctx", "n_threads"):
                if eng.get(k) is not None:
                    try:
                        cur_eng[k] = int(eng[k])
                    except (TypeError, ValueError):
                        pass
            self.cfg["engine"] = cur_eng
        self.cfg["configured"] = True
        C.save(self.cfg)
        self.core.set_language(lang)
        self.core.set_ai_name(self.cfg["ai_name"])
        # état initial clair : pas de moteur, message d'invite
        self.core.engine = None
        self.core.engine_state = "off"
        self.core._set_status("off", _.tr("status.not_installed"))
        return {"ok": True}

    # -- chat ---------------------------------------------------------------

    def send_chat(self, text, image_b64=None, image_name=""):
        path = None
        if image_b64:
            if len(image_b64) > 34 * 1024 * 1024:  # ~25 MB raw
                return {"ok": False, "error": _.tr("chat.big_image")}
            try:
                data = base64.b64decode(image_b64)
                out = os.path.join(C.data_dir(), "images")
                os.makedirs(out, exist_ok=True)
                ext = os.path.splitext(image_name or "img.png")[1] or ".png"
                path = os.path.join(out, "attach-" + datetime.datetime.now()
                                    .strftime("%Y%m%d-%H%M%S") + ext)
                with open(path, "wb") as f:
                    f.write(data)
            except Exception:
                return {"ok": False, "error": _.tr("chat.big_image")}
        self.core.send(text or "", path)
        return {"ok": True}

    def factory_reset(self):
        return self.core.factory_reset()

    def stop_generation(self):
        self.core.stop()

    def clear_chat(self):
        self.core.clear()

    def list_conversations(self):
        return self.core.list_conversations()

    def load_conversation(self, cid):
        return {"ok": self.core.load_conversation(cid)}

    def new_conversation(self):
        self.core.new_conversation()
        return {"ok": True}

    def delete_conversation(self, cid):
        self.core.delete_conversation(cid)
        return {"ok": True}

    def confirm_response(self, cid, ok):
        self.core.confirm_response(cid, ok)

    # -- models -------------------------------------------------------------

    def get_catalog(self):
        active = self.active_tier_name()
        remote_on = self.core.remote_active()
        remote_model = (self.core.remote_profile().get("model")
                        if remote_on else "")
        out = []
        for t in M.CATALOG:
            job = self.core.downloads.get(t.name)
            out.append({
                "name": t.name, "category": t.category, "power": t.power,
                "params": t.params, "size": t.size_str, "ram": t.ram_str,
                "desc": t.desc, "vision": t.is_vision,
                "installed": M.is_installed(t.name),
                # un modèle absent du disque ne peut pas être « actif »
                "active": t.name == active and M.is_installed(t.name),
                "downloading": bool(job and job.running),
                "recommended": t.name == SI.best_tier(t.category),
                "remote": False,
            })
        # modèles exposés par les API distantes activées (OpenAI / Anthropic /
        # compatible) : ils apparaissent dans la même liste, sans téléchargement.
        remote_entries = self.core.remote_models()
        # modèles cloud gratuits xKiro : testés en direct — si l'API ne répond
        # pas ils ne sont simplement pas listés
        seen = {e["tier"] for e in remote_entries}
        for rm in self.core.xkiro_free_models():
            if rm["tier"] not in seen:
                remote_entries.append(rm)
        for rm in remote_entries:
            out.append({
                "name": rm["name"], "tier": rm["tier"],
                "category": "remote", "power": rm["params"],
                "params": rm["base"], "size": rm["size"], "ram": rm["ram"],
                "desc": rm["desc"], "vision": False, "installed": True,
                "active": bool(remote_on and remote_on == rm["provider"]
                               and remote_model == rm["base"]),
                "downloading": False, "recommended": False, "remote": True,
            })
        return out

    def download_model(self, name):
        self.core.download_model(name)

    def cancel_download(self, name):
        self.core.cancel_download(name)

    def select_model(self, name):
        name = str(name or "")
        # modèle distant ? on route le chat vers l'API correspondante
        # (les entrées xKiro gratuites ne sont PAS dans remote_models() :
        #  il faut aussi regarder xkiro_free_models, sinon le clic sur une
        #  carte cloud ne fait rien et le chat reste « no model installed »)
        remotes = self.core.remote_models() + self.core.xkiro_free_models()
        for rm in remotes:
            if name in (rm["name"], rm["tier"]):
                self.core.select_remote(rm["provider"], rm["base"])
                return
        if self.core.remote_active():
            self.cfg.setdefault("remote", {})["active"] = ""
        self.core.select_model(name)

    def delete_model(self, name):
        self.core.delete_model(name)
        return {"ok": True, "name": name}

    # -- settings -----------------------------------------------------------

    def toggle_search(self):
        return {"on": self.core.toggle_search()}

    def toggle_reasoning(self):
        return {"on": self.core.toggle_reasoning()}

    def save_settings(self, updates):
        updates = updates or {}
        if "ai_name" in updates:
            self.core.set_ai_name(updates.pop("ai_name"))
        if "user_name" in updates:
            uname = (updates.pop("user_name") or "").strip()
            self.cfg.setdefault("profile", {})["name"] = uname
        if "language" in updates:
            self.core.set_language(updates.pop("language"))
        if "preset" in updates:
            self.cfg["preset"] = updates.pop("preset")
        if "system_prompt" in updates:
            self.cfg["system_prompt"] = updates.pop("system_prompt")
            self.cfg["system_prompt_custom"] = True
        if "uncensored" in updates:
            self.core.apply_settings({"uncensored": updates.pop("uncensored")})
            # le prompt système change : on recharge le moteur
            self.core._load_engine()
        if "engine" in updates:
            self.core.apply_settings({"engine": updates.pop("engine")})
        if "image" in updates:
            self.core.apply_settings({"image": updates.pop("image")})
        if "tools" in updates:
            self.core.apply_settings({"tools": updates.pop("tools")})
        if "ui" in updates:
            self.core.apply_settings({"ui": updates.pop("ui")})
        if "providers" in updates:
            incoming = updates.pop("providers") or {}
            providers = self.cfg.setdefault("providers", {})
            for name, prof in incoming.items():
                if not isinstance(prof, dict):
                    continue
                cur = dict(providers.get(name) or {})
                # une clé vide signifie « ne pas changer » : le champ est
                # masqué côté interface, on ne veut pas l'effacer par erreur
                if not prof.get("api_key"):
                    prof = {k: v for k, v in prof.items() if k != "api_key"}
                cur.update(prof)
                providers[name] = cur
            R = self.core.remote_active()
            if (self.cfg.get("remote") or {}).get("active") and not R:
                self.cfg.setdefault("remote", {})["active"] = ""
        if "remote" in updates:
            rem = updates.pop("remote") or {}
            cur = self.cfg.setdefault("remote", {})
            cur.update(rem)
        if "server" in updates:
            srv = updates.pop("server")
            was = self.core.server and self.core.server.running
            self.core.apply_settings({"server": srv})
            if was:
                self.core.stop_server()
            if srv.get("enabled"):
                self.core.start_server()
        if updates:
            self.core.apply_settings(updates)
        C.save(self.cfg)
        return {"ok": True}

    def start_server(self):
        return {"ok": self.core.start_server()}

    def stop_server(self):
        self.core.stop_server()
        return {"ok": True}

    # -- remote providers ----------------------------------------------------

    def list_provider_models(self, provider, profile=None):
        """Liste les modèles exposés par une API.

        ``profile`` permet de tester des valeurs non encore enregistrées
        (bouton « Charger les modèles » avec une clé qu'on vient de saisir).
        """
        from .. import remote as RM
        try:
            if profile:
                models = RM.list_models(provider, profile)
            else:
                models = self.core.list_provider_models(provider)
            return {"ok": True, "models": models, "count": len(models)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300], "models": []}

    def test_provider(self, provider, profile=None):
        """Test de connexion : on demande simplement la liste des modèles."""
        r = self.list_provider_models(provider, profile)
        if r.get("ok"):
            r["sample"] = r["models"][:8]
        return r

    # -- dashboard ----------------------------------------------------------

    def get_stats(self):
        """Spécifications & performances : live + agrégats + journaux."""
        return self.core.system_stats()

    def reset_stats(self):
        from .. import stats as STATS
        STATS.reset()
        return {"ok": True}
    def apply_recommended(self):
        rec = SI.recommendations()
        self.core.apply_settings({
            "engine": {"n_ctx": rec["n_ctx"], "n_threads": rec["threads"],
                       "max_tokens": rec["max_tokens"],
                       "temperature": rec["temperature"]}})
        return {"ok": True, "tier": rec["tier"]}

    # -- image generation ---------------------------------------------------

    def generate_image(self, prompt, size="512x512", steps=0, model="",
                       negative="", cfg_scale=0.0):
        self.core.generate_image(prompt or "", size=size,
                                 steps=int(steps or 0), model=model or "",
                                 negative=negative or "",
                                 cfg_scale=float(cfg_scale or 0))
        return {"ok": True}

    def image_engine_state(self):
        return self.core.image_engine_state()

    def install_image_engine(self):
        self.core.install_image_engine()
        return {"ok": True}

    def system_summary(self):
        return {"hardware": SI.summary_text(),
                "rec": {k: SI.recommendations()[k]
                        for k in ("tier", "threads", "n_ctx", "max_tokens",
                                  "temperature")}}

    def quit_app(self):
        import webview
        try:
            for w in webview.windows:
                w.destroy()
        except Exception:
            os._exit(0)