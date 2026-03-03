"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    graydient_exchange.py  (ENHANCED)                        ║
║            Local API-exchange layer for the Graydient platform              ║
║                                                                             ║
║  ENHANCEMENTS:                                                              ║
║  • Full Graydient API exposure (workflows, concepts, community, users)      ║
║  • Local HTTP API server for external app integration                       ║
║  • WebSocket support for real-time updates                                  ║
║  • Plugin-friendly architecture (Premiere Pro, After Effects, etc.)         ║
╚══════════════════════════════════════════════════════════════════════════════╝

OVERVIEW
════════
A broker between your local applications and the Graydient render API.
Instead of every app directly calling `graydient.render.create()`, you
register named WorkflowDefinitions once, then any part of your codebase
calls `exchange.run("name", input_dict)` and receives a shaped result dict.

                        ┌──────────────────────────────┐
  your_app_a.py  ──────►│                              │
  your_app_b.py  ──────►│  Exchange  (this module)     │──► Graydient API
  telegram_bot.py ─────►│                              │
  premiere_plugin ─────►│  HTTP API + WebSocket        │
                        └──────────────────────────────┘

INSTALLATION
════════════
    # 1. Install Python deps:
    pip install pydantic python-dotenv requests sseclient-py rich

    # 2. Install the Graydient SDK (extract the .tgz alongside your project):
    #    The graydient/ folder from the .tgz must be importable.
    #    Easiest: put it in the same directory as this file, OR run:
    pip install /path/to/graydient-python-v0_2.tgz

    # 3. Set your API key in a .env file:
    echo "GRAYDIENT_KEY=your_key_here" > .env

QUICK START
═══════════
    from graydient_exchange import Exchange, WorkflowDefinition, InputMapping, OutputMapping

    ex = Exchange()
    ex.register(WorkflowDefinition(
        name      = "portrait",
        workflow  = "qwen",
        input_map = InputMapping(prompt_key="user_text"),
        output_map= OutputMapping(image_url_key="result_url"),
    ))
    result = ex.run("portrait", {"user_text": "a samurai cat"})
    print(result["result_url"])

FULL API ACCESS
═══════════════
    # Browse available workflows
    workflows = ex.workflows.list()
    
    # Browse concepts/LoRAs
    concepts = ex.concepts.search("cyberpunk")
    
    # Browse community renders
    renders = ex.community.renders(search_term="fantasy")
    
    # Virtual user management
    otp = ex.virtual_user.send_otp("user@example.com")
    vuser = ex.virtual_user.confirm_otp(otp.id, "123456")

HTTP API SERVER (for external apps)
════════════════════════════════════
    # Start the HTTP API server
    ex.start_api_server(port=8787)
    
    # Now external apps can:
    # POST http://localhost:8787/api/v1/render
    # GET  http://localhost:8787/api/v1/workflows
    # GET  http://localhost:8787/api/v1/jobs/{job_id}

RUN SETUP CHECKER
═════════════════
    python setup_check.py
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

# ── dotenv: load .env if present ─────────────────────────────────────────────
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass   # dotenv is optional; set GRAYDIENT_KEY in env directly if needed

logger = logging.getLogger("graydient_exchange")

# ── NOTE: `import graydient` is intentionally LAZY (see _graydient() below) ──
_graydient_module = None

def _graydient():
    """
    Lazily import and return the graydient module.
    Called only when a render is actually dispatched.
    Raises ImportError with a helpful install message if not available.
    """
    global _graydient_module
    if _graydient_module is None:
        try:
            import graydient as _g
            _graydient_module = _g
        except ImportError as e:
            raise ImportError(
                "\n\n"
                "  ✗  Cannot import the Graydient SDK.\n\n"
                "  Fix one of the following:\n"
                "  • pip install /path/to/graydient-python-v0_2.tgz\n"
                "  • Copy the graydient/ folder next to this file\n"
                "  • pip install pydantic sseclient-py requests  (if graydient is present but deps are missing)\n\n"
                "  Then run:  python setup_check.py  to verify everything is ready.\n"
            ) from e
    return _graydient_module


# ══════════════════════════════════════════════════════════════════════════════
# Job lifecycle types
# ══════════════════════════════════════════════════════════════════════════════

class JobStatus(str, Enum):
    """
    Lifecycle states for a dispatched render job.

    PENDING   Job created, not yet sent to Graydient.
    RUNNING   SSE stream open, events arriving.
    DONE      rendering_done received, result available.
    ERROR     An error event or exception occurred.
    TIMEOUT   exchange.run() timed out waiting for completion.
    """
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"
    TIMEOUT = "timeout"


@dataclass
class JobEvent:
    """
    A single SSE event captured during a render job.

    Attributes
    ──────────
    timestamp   Unix epoch float — when this event arrived.
    raw         The raw event dict from the Graydient SSE stream.
    kind        Human-readable label derived from event keys:
                "rendering_progress" | "rendering_done" | "error" |
                "queued" | "started" | "heartbeat" | "unknown"

    Common raw event shapes
    ───────────────────────
    rendering_progress → {"rendering_progress": {"step": int, "total_steps": int}}
    rendering_done     → {"rendering_done": {"render_hash": str}}
    error              → {"error": str | dict}
    """
    timestamp : float
    raw       : Dict[str, Any]
    kind      : str = field(init=False)

    def __post_init__(self):
        for candidate in ("rendering_done", "rendering_progress", "error",
                          "queued", "started", "heartbeat"):
            if candidate in self.raw:
                self.kind = candidate
                return
        self.kind = "unknown"

    @property
    def age_seconds(self) -> float:
        """Seconds elapsed since this event arrived."""
        return time.time() - self.timestamp

    def __repr__(self):
        ts = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        return f"<JobEvent kind={self.kind!r} at {ts}>"


@dataclass
class JobRecord:
    """
    Complete lifecycle record for one dispatched render job.

    Created automatically by Exchange.run() / run_async().
    Passed to registered observers after every state change.
    Accessible via exchange.get_job(job_id) or exchange.job_history().

    Attributes
    ──────────
    job_id          UUID string — unique to this exchange dispatch.
    workflow_name   Logical workflow name (e.g. "portrait").
    workflow_slug   Graydient workflow slug (e.g. "qwen").
    input_data      Raw input dict from the calling application.
    mapped_params   Translated params sent to Graydient.
    status          Current JobStatus.
    events          Ordered list of JobEvent objects.
    result          Shaped result dict once DONE; None otherwise.
    error_message   Error description when status == ERROR.
    started_at      Unix timestamp of dispatch.
    finished_at     Unix timestamp of terminal state; None if still running.

    Computed properties
    ───────────────────
    elapsed_seconds      Wall-clock seconds from dispatch to now (or finish).
    render_hash          Graydient render_hash from the rendering_done event.
    progress_pct         0–100 float from latest rendering_progress; None if absent.
    latest_event_summary Short human-readable status string.
    """
    job_id        : str
    workflow_name : str
    workflow_slug : str
    input_data    : Dict[str, Any]
    mapped_params : Dict[str, Any]
    status        : JobStatus                = JobStatus.PENDING
    events        : List[JobEvent]           = field(default_factory=list)
    result        : Optional[Dict[str, Any]] = None
    error_message : Optional[str]            = None
    started_at    : float                    = field(default_factory=time.time)
    finished_at   : Optional[float]          = None

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or time.time()
        return end - self.started_at

    @property
    def render_hash(self) -> Optional[str]:
        for ev in reversed(self.events):
            if ev.kind == "rendering_done":
                return ev.raw.get("rendering_done", {}).get("render_hash")
        return None

    @property
    def progress_pct(self) -> Optional[float]:
        for ev in reversed(self.events):
            if ev.kind == "rendering_progress":
                data  = ev.raw.get("rendering_progress", {})
                step  = data.get("step", 0)
                total = data.get("total_steps", 0)
                if total > 0:
                    return min(100.0, (step / total) * 100)
        return None

    @property
    def latest_event_summary(self) -> str:
        if not self.events:
            return "pending…"
        ev = self.events[-1]
        if ev.kind == "rendering_progress":
            pct = self.progress_pct
            return f"rendering… {pct:.0f}%" if pct is not None else "rendering…"
        if ev.kind == "rendering_done":
            return f"done → {self.render_hash or '?'}"
        if ev.kind == "error":
            return f"error: {ev.raw.get('error', 'unknown')}"
        return ev.kind

    def to_dict(self) -> Dict[str, Any]:
        """Convert JobRecord to a dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "workflow_name": self.workflow_name,
            "workflow_slug": self.workflow_slug,
            "status": self.status.value,
            "progress_pct": self.progress_pct,
            "elapsed_seconds": self.elapsed_seconds,
            "render_hash": self.render_hash,
            "result": self.result,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def __repr__(self):
        return (
            f"<JobRecord {self.job_id[:8]} "
            f"workflow={self.workflow_name!r} "
            f"status={self.status.value} "
            f"elapsed={self.elapsed_seconds:.1f}s>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# InputMapping
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class InputMapping:
    """
    Translate your application's input dict into Graydient render kwargs.

    Parameters
    ──────────
    prompt_key : str | None
        Key in your input dict that holds the main prompt string.
        Falls back to looking for "prompt" directly if None.
        Example: InputMapping(prompt_key="user_text")
                 {"user_text": "a fox"} → prompt="a fox"

    negative_key : str | None
        Key for the negative prompt (things NOT to render).
        Example: InputMapping(negative_key="avoid")
                 {"avoid": "blurry"} → negative="blurry"

    image_key : str | None
        Key for an init-image URL (img2img / animation workflows).
        Maps to inputs["init_image"] in the Graydient request.
        The value must be a publicly accessible URL.

    seed_key : str | None
        Key for an integer seed. If absent or None, Graydient picks randomly.

    extra_inputs : dict[str, str]
        Static entries always added to the Graydient inputs dict
        (alongside init_image). Useful for permanently wired style images.

    slots : dict[str, str]
        Static Graydient workflow slots (node-level overrides).
        e.g. {"sampler": "dpmpp_2m", "steps": "30"}

    extra : dict[str, Any]
        Static kwargs always passed to render.create().
        e.g. {"guidance": 7.5, "num_images": 2, "format": "png"}

    transform : Callable[[dict], dict] | None
        fn(input_dict) -> dict  runs AFTER key mapping; its return value
        is merged on top and can override anything.
        Use for complex prompt building, conditional logic, etc.
    """
    prompt_key   : Optional[str]                     = None
    negative_key : Optional[str]                     = None
    image_key    : Optional[str]                     = None
    seed_key     : Optional[str]                     = None
    extra_inputs : Dict[str, str]                    = field(default_factory=dict)
    slots        : Dict[str, str]                    = field(default_factory=dict)
    extra        : Dict[str, Any]                    = field(default_factory=dict)
    transform    : Optional[Callable[[Dict], Dict]]  = None

    def apply(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply this mapping to a raw input dict; return Graydient kwargs.

        Useful for testing a mapping in isolation:
            m = InputMapping(prompt_key="text", seed_key="s")
            print(m.apply({"text": "a cat", "s": 7}))
            # → {"prompt": "a cat", "seed": 7}
        """
        params: Dict[str, Any] = {}

        # Prompt
        pk = self.prompt_key or "prompt"
        if pk in raw:
            params["prompt"] = raw[pk]

        # Negative
        if self.negative_key and self.negative_key in raw:
            params["negative"] = raw[self.negative_key]

        # Seed
        sk = self.seed_key or "seed"
        if sk in raw and raw[sk] is not None:
            params["seed"] = int(raw[sk])

        # Inputs (images etc.)
        inputs: Dict[str, str] = dict(self.extra_inputs)
        if self.image_key and raw.get(self.image_key):
            inputs["init_image"] = raw[self.image_key]
        if inputs:
            params["inputs"] = inputs

        # Slots
        if self.slots:
            params["slots"] = dict(self.slots)

        # Static extras
        params.update(self.extra)

        # Custom transform (runs last, can override everything above)
        if self.transform:
            params.update(self.transform(raw))

        return params


# ══════════════════════════════════════════════════════════════════════════════
# OutputMapping
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OutputMapping:
    """
    Reshape a completed Graydient Render into your application's result dict.

    Parameters
    ──────────
    image_url_key : str
        Key for the primary still-image URL. Default: "image_url".

    video_url_key : str
        Key for the primary video URL (mp4). Default: "video_url".
        mp4 URLs are auto-detected from the render's media list.

    metadata_key : str | None
        If set, includes render.metadata_fields under this key.

    render_hash_key : str | None
        If set, includes the Graydient render_hash under this key.
        Useful for referencing or re-fetching the render later.

    transform : Callable[[dict], dict] | None
        fn(result_dict) -> dict  applied last; full control over final shape.

    URL detection logic
    ───────────────────
    1. Scan media list for a URL ending in ".mp4" → video_url_key
    2. First non-mp4 media URL or fallback .url → image_url_key
    Both keys can be present if the render produces both.
    """
    image_url_key   : str                            = "image_url"
    video_url_key   : str                            = "video_url"
    metadata_key    : Optional[str]                  = None
    render_hash_key : Optional[str]                  = None
    transform       : Optional[Callable[[Dict], Dict]] = None

    def apply(self, render) -> Dict[str, Any]:
        """Convert a Graydient Render object into an app-friendly result dict."""
        result: Dict[str, Any] = {}

        if render.images:
            img = render.images[0]
            image_url = None
            if img.media:
                mp4 = next((m["url"] for m in img.media
                            if m.get("url", "").endswith(".mp4")), None)
                if mp4:
                    result[self.video_url_key] = mp4
                    image_url = mp4
                else:
                    image_url = img.media[0].get("url")
            image_url = image_url or getattr(img, "url", None)
            if image_url:
                result[self.image_url_key] = image_url

        if self.render_hash_key and getattr(render, "render_hash", None):
            result[self.render_hash_key] = render.render_hash

        if self.metadata_key and getattr(render, "metadata_fields", None):
            result[self.metadata_key] = render.metadata_fields

        if self.transform:
            result = self.transform(result)

        return result


# ══════════════════════════════════════════════════════════════════════════════
# WorkflowDefinition
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class WorkflowDefinition:
    """
    A named, reusable spec for one Graydient workflow call.

    Register with exchange.register(definition).
    Dispatch with exchange.run("name", input_dict).

    Parameters
    ──────────
    name : str
        Logical name. Must be unique per Exchange instance.
        Use lowercase-with-hyphens: "portrait", "animate-emote".

    workflow : str
        Graydient workflow slug. List all: exchange.workflows.list()
        Examples: "qwen", "edit-qwen", "animate-wan22"

    default_params : dict
        Static kwargs always passed to render.create(), before input mapping.
        Per-call mapped params override these.
        e.g. {"num_images": 1, "format": "png", "guidance": 7.5}

    input_map : InputMapping
        How the calling app's dict → Graydient params.

    output_map : OutputMapping
        How the completed Render → caller's result dict.

    progressive : bool
        Whether to use progressive_return=True. Default True.
        Enables partial renders and progress events during rendering.

    description : str
        Human-readable label shown in Display UI and logs.

    tags : list[str]
        Optional grouping tags for filtering in Display UI.
    """
    name           : str
    workflow       : str
    default_params : Dict[str, Any]   = field(default_factory=dict)
    input_map      : InputMapping     = field(default_factory=InputMapping)
    output_map     : OutputMapping    = field(default_factory=OutputMapping)
    progressive    : bool             = True
    description    : str              = ""
    tags           : List[str]        = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            raise ValueError("WorkflowDefinition.name must not be empty")
        if not self.workflow:
            raise ValueError("WorkflowDefinition.workflow (slug) must not be empty")


# ══════════════════════════════════════════════════════════════════════════════
# Internal: SSE stream handler builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_stream_handler(
    record      : JobRecord,
    output_map  : OutputMapping,
    observers   : List[Callable[[JobRecord], None]],
    on_progress : Optional[Callable[[Dict], None]] = None,
) -> Callable:
    """
    Build and return the SSE callback for one render job.
    Passed as stream= to graydient.render.create().

    Responsibilities:
    1. Wrap each raw event in a JobEvent; append to record.events.
    2. Update record.status.
    3. On rendering_done: fetch Render, apply OutputMapping, store result.
    4. On error: store message, mark ERROR.
    5. Notify all Exchange observers after every state change.
    6. Call per-call on_progress hook if provided.
    """
    def _notify():
        for obs in observers:
            try:
                obs(record)
            except Exception as exc:
                logger.warning("observer raised: %s", exc)

    def handler(event: Dict):
        record.events.append(JobEvent(timestamp=time.time(), raw=event))
        record.status = JobStatus.RUNNING

        if on_progress:
            try:
                on_progress(event)
            except Exception as exc:
                logger.warning("on_progress raised: %s", exc)

        if "rendering_done" in event:
            render_hash = event["rendering_done"].get("render_hash")
            if render_hash:
                try:
                    g             = _graydient()
                    render        = g.render.info(render_hash)
                    record.result = output_map.apply(render)
                    record.status = JobStatus.DONE
                    record.finished_at = time.time()
                    logger.info("[%s] done → %s", record.job_id[:8], render_hash)
                except Exception as exc:
                    record.status        = JobStatus.ERROR
                    record.error_message = str(exc)
                    record.result        = {"error": str(exc), "render_hash": render_hash}
                    record.finished_at   = time.time()
                    logger.error("[%s] error fetching result: %s", record.job_id[:8], exc)
            _notify()

        elif "error" in event:
            record.status        = JobStatus.ERROR
            record.error_message = str(event.get("error", "unknown error"))
            record.finished_at   = time.time()
            logger.error("[%s] render error: %s", record.job_id[:8], record.error_message)
            _notify()

        else:
            _notify()

    return handler


# ══════════════════════════════════════════════════════════════════════════════
# API Sub-modules (NEW - expose full Graydient API)
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowsAPI:
    """Access to Graydient workflow discovery."""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
    
    def list(self, search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available workflows from Graydient.
        
        Parameters
        ──────────
        search_term : str | None
            Optional search filter for workflow names.
            
        Returns
        ───────
        List of workflow dicts with keys:
            - name: workflow slug (e.g., "qwen", "animate-wan22")
            - description: human-readable description
            - platform: execution platform
            - supports_txt2img, supports_img2img, etc.: capability flags
        """
        g = _graydient()
        workflows = g.workflow.all(search_term=search_term, api_key=self._api_key)
        return [
            {
                "name": w.slug,
                "description": w.description or "",
                "platform": w.platform,
                "version": w.version,
                "supports_txt2img": w.supports_txt2img,
                "supports_img2img": w.supports_img2img,
                "supports_txt2vid": w.supports_txt2vid,
                "supports_vid2vid": w.supports_vid2vid,
                "supports_img2vid": w.supports_img2vid,
                "supports_low_memory": w.supports_low_memory,
                "is_public": w.is_public,
            }
            for w in workflows
        ]
    
    def get(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific workflow by slug."""
        workflows = self.list()
        for w in workflows:
            if w["name"] == slug:
                return w
        return None


class ConceptsAPI:
    """Access to Graydient concepts (LoRAs, embeddings, etc.)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
    
    def all(self, search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available concepts from Graydient.
        
        Parameters
        ──────────
        search_term : str | None
            Optional search filter for concept names.
            
        Returns
        ───────
        List of concept dicts with keys:
            - name: concept name/token
            - description: concept description
            - type: concept type (e.g., "lora", "embedding")
            - model_family: compatible model family
            - is_nsfw: NSFW flag
            - tags: list of tags
        """
        g = _graydient()
        concepts = g.concept.all(search_term=search_term, api_key=self._api_key)
        return [
            {
                "name": c.name,
                "token": c.token,
                "description": c.description or "",
                "type": c.type,
                "subtype_1": c.subtype_1,
                "subtype_2": c.subtype_2,
                "model_family": c.model_family,
                "is_nsfw": c.is_nsfw,
                "tags": c.tags or [],
                "concept_hash": c.concept_hash,
            }
            for c in concepts
        ]
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search concepts by query string."""
        return self.all(search_term=query)


class CommunityAPI:
    """Access to Graydient community renders."""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
    
    def renders(self, search_term: Optional[str] = None, only_music: bool = False) -> List[Dict[str, Any]]:
        """
        Browse community renders from Graydient.
        
        Parameters
        ──────────
        search_term : str | None
            Optional search filter.
        only_music : bool
            If True, only return music/audio renders.
            
        Returns
        ───────
        List of render dicts with keys:
            - render_hash: unique render identifier
            - prompt: generation prompt
            - images: list of image URLs
            - has_been_rendered: completion status
        """
        g = _graydient()
        renders = g.community.renders(
            search_term=search_term,
            api_key=self._api_key,
            only_music=only_music
        )
        return [
            {
                "render_hash": r.render_hash,
                "prompt": r.prompt,
                "images": [
                    {"url": img.url, "media": img.media}
                    for img in (r.images or [])
                ],
                "has_been_rendered": r.has_been_rendered,
                "metadata_fields": r.metadata_fields,
            }
            for r in renders
        ]


class VirtualUserAPI:
    """Virtual user OTP authentication management."""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
    
    def send_otp(self, email: str) -> Dict[str, str]:
        """
        Send an OTP code to the specified email address.
        
        Returns
        ───────
        Dict with "otp_id" key to pass to confirm_otp().
        """
        g = _graydient()
        otp = g.virtual_user.create(email, {"source": "graydient_exchange"})
        return {"otp_id": otp.id}
    
    def confirm_otp(self, otp_id: str, code: str) -> Dict[str, Any]:
        """
        Confirm an OTP code and get the virtual user ID.
        
        Returns
        ───────
        Dict with virtual user details including "id".
        """
        g = _graydient()
        from graydient.abstract_types import OTP
        otp = OTP(id=otp_id)
        vuser = g.virtual_user.confirm(otp, code)
        return {
            "id": vuser.id,
            "data": vuser.data,
        }
    
    def info(self, user_id: str) -> Dict[str, Any]:
        """Get information about a virtual user by ID."""
        g = _graydient()
        vuser = g.virtual_user.info(user_id)
        return {
            "id": vuser.id,
            "data": vuser.data,
        }
    
    def all_users(self) -> List[Dict[str, Any]]:
        """List all virtual users for this API key."""
        g = _graydient()
        users = g.virtual_user.all()
        return [{"id": u.id, "data": u.data} for u in users]


# ══════════════════════════════════════════════════════════════════════════════
# Exchange
# ══════════════════════════════════════════════════════════════════════════════

class Exchange:
    """
    Central broker for all Graydient workflow calls across your applications.

    • Holds a registry of WorkflowDefinitions (name → definition).
    • Translates input dicts using each definition's InputMapping.
    • Dispatches render jobs to the Graydient API via streaming SSE.
    • Collects all events into JobRecord objects.
    • Translates completed renders into shaped result dicts.
    • Notifies registered observers of every status change.
    • Provides access to full Graydient API via sub-modules.

    Constructor
    ───────────
    Exchange(api_key=None)
        api_key: explicit key. If None, uses GRAYDIENT_KEY env var.

    NOTE: importing this module does NOT import graydient. The SDK is only
    loaded when you first call run() / run_async(). This means setup_check.py
    and the viewer can run even when the SDK isn't installed yet.
    
    API Sub-modules
    ───────────────
    exchange.workflows    → WorkflowsAPI (list, discover workflows)
    exchange.concepts     → ConceptsAPI (browse LoRAs, embeddings)
    exchange.community    → CommunityAPI (browse community renders)
    exchange.virtual_user → VirtualUserAPI (OTP authentication)
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key    : Optional[str]                      = api_key or os.environ.get("GRAYDIENT_KEY")
        self._definitions: Dict[str, WorkflowDefinition]     = {}
        self._observers  : List[Callable[[JobRecord], None]] = []
        self._records    : Dict[str, JobRecord]               = {}
        
        # Initialize API sub-modules
        self._workflows = WorkflowsAPI(self._api_key)
        self._concepts = ConceptsAPI(self._api_key)
        self._community = CommunityAPI(self._api_key)
        self._virtual_user = VirtualUserAPI(self._api_key)
        
        # API server (lazy init)
        self._api_server = None

    # ── API Sub-modules ───────────────────────────────────────────────────────
    
    @property
    def workflows(self) -> WorkflowsAPI:
        """Access workflow discovery API."""
        return self._workflows
    
    @property
    def concepts(self) -> ConceptsAPI:
        """Access concept/LoRA discovery API."""
        return self._concepts
    
    @property
    def community(self) -> CommunityAPI:
        """Access community renders API."""
        return self._community
    
    @property
    def virtual_user(self) -> VirtualUserAPI:
        """Access virtual user OTP API."""
        return self._virtual_user

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, definition: WorkflowDefinition) -> "Exchange":
        """
        Register a WorkflowDefinition under its logical name.
        Overwrites silently if the name already exists (handy for hot-reload).
        Returns self for chaining: ex.register(a).register(b).register(c)
        """
        self._definitions[definition.name] = definition
        logger.info("registered: %r → slug=%r", definition.name, definition.workflow)
        return self

    def unregister(self, name: str) -> "Exchange":
        """Remove a registered workflow by logical name. Returns self."""
        self._definitions.pop(name, None)
        return self

    def list_workflows(self) -> List[Dict[str, Any]]:
        """Return summary dicts for all registered workflow definitions."""
        return [
            {"name": d.name, "workflow": d.workflow,
             "description": d.description, "tags": d.tags}
            for d in self._definitions.values()
        ]

    # ── Observers ─────────────────────────────────────────────────────────────

    def add_observer(self, callback: Callable[[JobRecord], None]) -> "Exchange":
        """
        Register a callback called after every job state change.

        The callback receives the mutated JobRecord. Use observers to drive
        UIs, logging, databases, or downstream integrations without coupling
        them to individual run() calls.

            def log_obs(record: JobRecord):
                print(f"[{record.job_id[:8]}] {record.status.value}")
            exchange.add_observer(log_obs)
        """
        self._observers.append(callback)
        return self

    def remove_observer(self, callback: Callable[[JobRecord], None]) -> "Exchange":
        """Remove a previously registered observer callback."""
        try:
            self._observers.remove(callback)
        except ValueError:
            pass
        return self

    # ── Job history ───────────────────────────────────────────────────────────

    def job_history(self, limit: int = 100) -> List[JobRecord]:
        """Return recent JobRecords, most recent first."""
        records = sorted(self._records.values(),
                         key=lambda r: r.started_at, reverse=True)
        return records[:limit]

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve a specific JobRecord by its exchange job_id UUID."""
        return self._records.get(job_id)

    # ── Synchronous dispatch ──────────────────────────────────────────────────

    def run(
        self,
        name          : str,
        input_data    : Dict[str, Any],
        on_progress   : Optional[Callable[[Dict], None]] = None,
        timeout       : float = 300,
        poll_interval : float = 0.05,
    ) -> Dict[str, Any]:
        """
        Dispatch a workflow job and block until it completes.

        Parameters
        ──────────
        name          Registered logical workflow name.
        input_data    Dict from your application; translated by InputMapping.
        on_progress   Optional fn(event_dict) called for every SSE event.
        timeout       Max seconds to wait. Default 300.
        poll_interval Seconds between completion checks. Default 0.05.

        Returns
        ───────
        dict  Shaped by OutputMapping. Contains "error" key on failure.
        """
        definition, record = self._prepare_job(name, input_data)
        handler = _build_stream_handler(record, definition.output_map,
                                        self._observers, on_progress)
        try:
            g = _graydient()
            g.render.create(
                workflow           = definition.workflow,
                progressive_return = definition.progressive,
                stream             = handler,
                api_key            = self._api_key,
                **record.mapped_params
            )
        except Exception as exc:
            record.status        = JobStatus.ERROR
            record.error_message = str(exc)
            record.finished_at   = time.time()
            logger.error("render.create raised: %s", exc)
            return {"error": str(exc)}

        deadline = time.time() + timeout
        while record.status not in (JobStatus.DONE, JobStatus.ERROR):
            if time.time() > deadline:
                record.status      = JobStatus.TIMEOUT
                record.finished_at = time.time()
                for obs in self._observers:
                    try: obs(record)
                    except Exception: pass
                return {"error": f"timeout after {timeout}s for '{name}'"}
            time.sleep(poll_interval)

        return record.result or {"error": record.error_message or "unknown error"}

    # ── Asynchronous dispatch ─────────────────────────────────────────────────

    def run_async(
        self,
        name          : str,
        input_data    : Dict[str, Any],
        callback      : Callable[[Dict], None],
        on_progress   : Optional[Callable[[Dict], None]] = None,
        timeout       : float = 300,
    ) -> JobRecord:
        """
        Dispatch a workflow job in a daemon background thread.
        Returns immediately; callback(result_dict) is called when done.

        Parameters
        ──────────
        name          Registered workflow name.
        input_data    Application input dict.
        callback      fn(result_dict) called when render completes.
        on_progress   Optional fn(event_dict) per SSE event.
        timeout       Max seconds per job. Default 300.

        Returns
        ───────
        JobRecord  Initially PENDING; mutated in-place as events arrive.
        """
        import threading
        definition, record = self._prepare_job(name, input_data)
        handler = _build_stream_handler(record, definition.output_map,
                                        self._observers, on_progress)

        def _worker():
            try:
                g = _graydient()
                g.render.create(
                    workflow           = definition.workflow,
                    progressive_return = definition.progressive,
                    stream             = handler,
                    api_key            = self._api_key,
                    **record.mapped_params
                )
            except Exception as exc:
                record.status        = JobStatus.ERROR
                record.error_message = str(exc)
                record.finished_at   = time.time()
                for obs in self._observers:
                    try: obs(record)
                    except Exception: pass

            deadline = time.time() + timeout
            while record.status not in (JobStatus.DONE, JobStatus.ERROR):
                if time.time() > deadline:
                    record.status = JobStatus.TIMEOUT
                    record.finished_at = time.time()
                    break
                time.sleep(0.05)

            try:
                callback(record.result or {"error": record.error_message or "unknown"})
            except Exception as exc:
                logger.error("run_async callback raised: %s", exc)

        t = threading.Thread(target=_worker, daemon=True, name=f"gex-{record.job_id[:8]}")
        t.start()
        return record

    # ── Batch dispatch ────────────────────────────────────────────────────────

    def run_batch(
        self,
        name          : str,
        inputs        : List[Dict[str, Any]],
        on_progress   : Optional[Callable[[int, Dict], None]] = None,
        sleep_between : float = 0,
        timeout       : float = 300,
    ) -> List[Dict[str, Any]]:
        """
        Run the same workflow for a list of input dicts sequentially.

        Parameters
        ──────────
        name          Registered workflow name.
        inputs        List of input dicts.
        on_progress   Optional fn(index, event_dict).
        sleep_between Seconds to pause between jobs (rate limiting).
        timeout       Per-job timeout seconds.

        Returns
        ───────
        list[dict]  Results in same order as inputs.
        """
        results = []
        for idx, input_data in enumerate(inputs):
            logger.info("batch item %d/%d", idx + 1, len(inputs))
            prg = (lambda i: lambda evt: on_progress(i, evt))(idx) if on_progress else None
            results.append(self.run(name, input_data, on_progress=prg, timeout=timeout))
            if sleep_between and idx < len(inputs) - 1:
                time.sleep(sleep_between)
        return results

    # ── HTTP API Server (NEW - for external app integration) ──────────────────
    
    def start_api_server(self, port: int = 8787, host: str = "127.0.0.1") -> str:
        """
        Start an HTTP API server for external application integration.
        
        This allows external apps (Premiere Pro, After Effects, etc.) to
        interact with the Exchange via HTTP requests.
        
        Parameters
        ──────────
        port : int
            Port to listen on. Default 8787.
        host : str
            Host to bind to. Default 127.0.0.1 (localhost only).
            
        Returns
        ───────
        str — The base URL of the API server.
        
        API Endpoints
        ─────────────
        POST /api/v1/render
            Submit a render job.
            Body: {"workflow": "name", "input": {...}}
            Returns: {"job_id": "...", "status": "pending"}
            
        GET  /api/v1/jobs/{job_id}
            Get job status and result.
            Returns: JobRecord as dict
            
        GET  /api/v1/jobs
            List recent jobs.
            Returns: [{"job_id": "...", "status": "...", ...}]
            
        GET  /api/v1/workflows
            List registered workflows.
            Returns: [{"name": "...", "workflow": "..."}]
            
        GET  /api/v1/graydient/workflows
            List available Graydient workflows.
            
        GET  /api/v1/graydient/concepts
            Search Graydient concepts.
            Query: ?q=search_term
        """
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading
        
        exchange = self
        
        class APIHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress request logs
            
            def _json_response(self, data: dict, status: int = 200):
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            
            def _read_body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                if length:
                    return json.loads(self.rfile.read(length).decode("utf-8"))
                return {}
            
            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
            
            def do_GET(self):
                if self.path == "/api/v1/workflows":
                    self._json_response({"workflows": exchange.list_workflows()})
                elif self.path == "/api/v1/jobs":
                    jobs = [r.to_dict() for r in exchange.job_history()]
                    self._json_response({"jobs": jobs})
                elif self.path.startswith("/api/v1/jobs/"):
                    job_id = self.path.split("/")[-1]
                    job = exchange.get_job(job_id)
                    if job:
                        self._json_response(job.to_dict())
                    else:
                        self._json_response({"error": "Job not found"}, 404)
                elif self.path == "/api/v1/graydient/workflows":
                    try:
                        workflows = exchange.workflows.list()
                        self._json_response({"workflows": workflows})
                    except Exception as e:
                        self._json_response({"error": str(e)}, 500)
                elif self.path == "/api/v1/graydient/concepts":
                    query = self.path.split("?q=")[-1] if "?q=" in self.path else None
                    try:
                        concepts = exchange.concepts.search(query) if query else exchange.concepts.all()
                        self._json_response({"concepts": concepts})
                    except Exception as e:
                        self._json_response({"error": str(e)}, 500)
                elif self.path == "/api/v1/health":
                    self._json_response({"status": "ok", "exchange": "running"})
                else:
                    self._json_response({"error": "Not found"}, 404)
            
            def do_POST(self):
                if self.path == "/api/v1/render":
                    body = self._read_body()
                    workflow_name = body.get("workflow")
                    input_data = body.get("input", {})
                    
                    if not workflow_name:
                        self._json_response({"error": "workflow is required"}, 400)
                        return
                    
                    if workflow_name not in exchange._definitions:
                        self._json_response({
                            "error": f"Workflow '{workflow_name}' not registered"
                        }, 404)
                        return
                    
                    # Start async render
                    result_container = {}
                    
                    def callback(result):
                        result_container["result"] = result
                    
                    record = exchange.run_async(workflow_name, input_data, callback)
                    
                    self._json_response({
                        "job_id": record.job_id,
                        "status": record.status.value,
                        "message": "Render started. Poll /api/v1/jobs/{job_id} for status."
                    }, 202)
                else:
                    self._json_response({"error": "Not found"}, 404)
        
        server = HTTPServer((host, port), APIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        self._api_server = server
        url = f"http://{host}:{port}"
        logger.info("API server started at %s", url)
        return url
    
    def stop_api_server(self):
        """Stop the HTTP API server if running."""
        if self._api_server:
            self._api_server.shutdown()
            self._api_server = None
            logger.info("API server stopped")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_definition(self, name: str) -> WorkflowDefinition:
        if name not in self._definitions:
            avail = ", ".join(self._definitions) or "(none registered)"
            raise KeyError(f"No workflow named {name!r}. Available: {avail}")
        return self._definitions[name]

    def _build_params(self, definition: WorkflowDefinition, input_data: Dict) -> Dict[str, Any]:
        """Merge default_params + input mapping. Mapped params override defaults."""
        params = dict(definition.default_params)
        params.update(definition.input_map.apply(input_data))
        return params

    def _prepare_job(self, name: str, input_data: Dict) -> tuple:
        """Create a JobRecord, store it, return (definition, record)."""
        definition    = self._get_definition(name)
        mapped_params = self._build_params(definition, input_data)
        record        = JobRecord(
            job_id        = str(uuid.uuid4()),
            workflow_name = name,
            workflow_slug = definition.workflow,
            input_data    = input_data,
            mapped_params = mapped_params,
        )
        self._records[record.job_id] = record
        return definition, record


# ══════════════════════════════════════════════════════════════════════════════
# Convenience exports
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "Exchange",
    "WorkflowDefinition",
    "InputMapping",
    "OutputMapping",
    "JobRecord",
    "JobStatus",
    "JobEvent",
    "WorkflowsAPI",
    "ConceptsAPI",
    "CommunityAPI",
    "VirtualUserAPI",
]
