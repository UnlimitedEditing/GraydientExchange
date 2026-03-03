# Graydient CLI Toolkit - Implementation Task Plan

## Overview

This toolkit bridges the Graydient SaaS API to a local CLI, enabling dynamic method discovery, Telegram-style command inputs, and an interactive tutorial system for onboarding users.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         GRAYDIENT CLI TOOLKIT                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │  MethodRegistry  │◄───│  Graydient API   │    │ PreviewDataset   │          │
│  │  (Discovery)     │    │  (Workflows/     │    │  (Image/Video    │          │
│  │                  │    │   Concepts)      │    │   Previews)      │          │
│  └────────┬─────────┘    └──────────────────┘    └──────────────────┘          │
│           │                                                                     │
│           ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐          │
│  │                    CommandParserEngine                            │          │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │          │
│  │  │ /method     │  │ [negative]  │  │ --traditional-flag      │   │          │
│  │  │ (positive)  │  │ (negative)  │  │ (legacy support)        │   │          │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │          │
│  └────────────────────────┬─────────────────────────────────────────┘          │
│                           │                                                     │
│           ┌───────────────┼───────────────┐                                    │
│           ▼               ▼               ▼                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                             │
│  │   Input     │  │   Method    │  │   Config    │                             │
│  │  Modifier   │  │  Validator  │  │   Manager   │                             │
│  └─────────────┘  └─────────────┘  └─────────────┘                             │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                      INTERACTIVE TUTORIAL SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │ TutorialEngine   │    │ HighlightOverlay │    │ AnnotationPanel  │          │
│  │ (Step Manager)   │    │ (Screen Regions) │    │ (Text/Media)     │          │
│  └────────┬─────────┘    └──────────────────┘    └──────────────────┘          │
│           │                                                                     │
│           ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐          │
│  │                      TutorialEditor                               │          │
│  │  - Create tutorials via JSON or GUI                              │          │
│  │  - Define highlight regions (x, y, w, h)                         │          │
│  │  - Add annotations with image/video placeholders                 │          │
│  │  - Export/Import tutorial definitions                            │          │
│  └──────────────────────────────────────────────────────────────────┘          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### 1. MethodRegistry (`method_registry.py`)
**Purpose:** Dynamic discovery and caching of workflows and concepts from Graydient API

**Features:**
- Fetch all available workflows from `/workflows` endpoint
- Fetch all concepts from `/concepts` endpoint
- Cache results with TTL (time-to-live) for performance
- Auto-refresh when cache expires
- Map workflow slugs to friendly command names
- Store method metadata (description, parameters, capabilities)

**Key Classes:**
- `MethodRegistry` - Main registry with caching
- `WorkflowMethod` - Represents a workflow method
- `ConceptMethod` - Represents a concept/LoRA method
- `MethodMetadata` - Metadata container for any method

**API Integration:**
```python
# From set1-api.txt - workflow.py
workflows = g.workflow.all(search_term=search_term, api_key=api_key)

# From set1-api.txt - concept.py  
concepts = g.concept.all(search_term=search_term, api_key=api_key)
```

---

### 2. CommandParserEngine (`command_parser.py`)
**Purpose:** Parse Telegram-style commands with /method and [negative] handle support

**Features:**
- Parse `/method` syntax (positive handles)
- Parse `[negative]` syntax (negative handles)
- Support legacy `--flag` syntax for backward compatibility
- Auto-complete method names from registry
- Validate parameters against method metadata
- Convert parsed commands to Exchange-compatible format

**Command Syntax:**
```
# Positive handles (what to include)
/draw a beautiful landscape --seed 42
/animate my character walking
/style transfer to oil painting

# Negative handles (what to exclude)
[blurry, low quality, distorted]
[nsfw, violence]

# Combined usage
/draw a cyberpunk city [blurry, low quality] --seed 123

# Legacy support (still works)
--input prompt="a cat" --seed=42
```

**Key Classes:**
- `CommandParserEngine` - Main parser
- `ParsedCommand` - Result container
- `HandleType` - Enum for POSITIVE, NEGATIVE, LEGACY

---

### 3. MethodMetadata (`method_metadata.py`)
**Purpose:** Store and manage detailed information about each method

**Features:**
- Store method descriptions
- Define parameter schemas (type, default, min, max, help text)
- Track method capabilities (txt2img, img2img, txt2vid, etc.)
- Link to preview images/videos
- Store example prompts
- Version tracking for API changes

**Data Structure:**
```python
@dataclass
class MethodMetadata:
    slug: str                    # API identifier
    display_name: str            # Human-readable name
    description: str             # Full description
    category: str                # "workflow" or "concept"
    capabilities: List[str]      # ["txt2img", "img2img", ...]
    parameters: List[ParameterDef]
    preview_media: List[str]     # Paths to preview files
    examples: List[str]          # Example prompts
    version: int                 # API version
    last_updated: datetime
```

---

### 4. PreviewDataset (`preview_dataset.py`)
**Purpose:** Manage image and video previews for each method

**Features:**
- Download and cache preview images/videos
- Organize by method slug
- Support multiple previews per method (slideshow)
- Lazy loading for performance
- Optional: Generate previews on-demand

**Directory Structure:**
```
previews/
├── workflows/
│   ├── qwen/
│   │   ├── preview_01.jpg
│   │   ├── preview_02.jpg
│   │   └── example_video.mp4
│   ├── edit-qwen/
│   │   └── preview_01.jpg
│   └── animate-wan22/
│       └── demo_animation.mp4
└── concepts/
    ├── lora-style-1/
    │   └── preview.jpg
    └── embedding-face/
        └── preview.jpg
```

---

### 5. InputModifier (`input_modifier.py`)
**Purpose:** Modify and transform CLI inputs before sending to Exchange

**Features:**
- Transform `/method` commands to Exchange format
- Apply negative handles to prompts
- Validate inputs against method schemas
- Auto-fill default parameters
- Support parameter presets/profiles
- Chain multiple modifiers

**Integration with Existing Code:**
```python
# From set2-cli.txt - graydient_exchange.py
exchange.run("workflow_name", input_data)

# Toolkit wraps this:
modified_input = input_modifier.transform(parsed_command)
exchange.run(modified_input.workflow, modified_input.params)
```

---

### 6. ConfigManager (`config_manager.py`)
**Purpose:** Manage user preferences and method handle settings

**Features:**
- Save/load user preferences (JSON/YAML)
- Configure preferred method handle style:
  - `/method` only (Telegram-style)
  - `[negative]` only
  - Both combined
  - Legacy `--flag` mode
- Custom method aliases
- Default parameter values
- Theme preferences for display

**Config File:**
```yaml
# ~/.graydient_toolkit/config.yaml
input_style: "telegram"  # telegram, legacy, mixed
method_aliases:
  "d": "draw"
  "a": "animate"
  "s": "style"
defaults:
  seed: 42
  guidance: 7.5
  steps: 30
display:
  theme: "phosphor"
  auto_open_viewer: true
```

---

### 7. TutorialEngine (`tutorial/`)
**Purpose:** Interactive onboarding with screen highlighting and annotations

**Features:**
- Step-by-step tutorial progression
- Highlight screen regions with overlays
- Display annotations with text/images/videos
- Support for multiple tutorials
- Progress tracking
- Skip/resume functionality

**Components:**
- `TutorialEngine` - Core step manager
- `HighlightOverlay` - Screen region highlighting (CSS/JS)
- `AnnotationPanel` - Display tutorial content
- `TutorialDefinition` - Tutorial data structure

**Tutorial Definition Format:**
```json
{
  "id": "getting-started",
  "title": "Getting Started with Graydient",
  "steps": [
    {
      "id": "step-1",
      "title": "Authentication",
      "highlight": {"x": 100, "y": 50, "width": 200, "height": 40},
      "annotation": {
        "title": "Enter your API Key",
        "text": "Get your API key from https://app.graydient.ai/account",
        "media": {
          "type": "image",
          "src": "tutorials/api-key-location.png"
        }
      },
      "actions": ["click", "input"]
    }
  ]
}
```

---

### 8. TutorialEditor (`tutorial_editor.py`)
**Purpose:** GUI tool for creating and editing tutorials

**Features:**
- Visual region selector for highlights
- WYSIWYG annotation editor
- Media upload (images/videos)
- Step reordering
- Preview mode
- Export to JSON

**UI Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  Tutorial Editor                              [Preview] │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────────────────────┐   │
│  │ Steps       │  │ Step Editor                     │   │
│  │ ─────────   │  │ ─────────────────────────────── │   │
│  │ 1. Auth ▶   │  │ Title: [Enter API Key         ] │   │
│  │ 2. Command  │  │                                 │   │
│  │ 3. Render   │  │ Highlight Region:               │   │
│  │             │  │ [Select on Screen]              │   │
│  │ [+ Add]     │  │ X: [100] Y: [50] W: [200] H:[40]│   │
│  │             │  │                                 │   │
│  │             │  │ Annotation:                     │   │
│  │             │  │ [Text editor...]                │   │
│  │             │  │                                 │   │
│  │             │  │ Media: [Upload Image/Video]     │   │
│  │             │  │                                 │   │
│  │             │  │ [Save Step] [Delete Step]       │   │
│  └─────────────┘  └─────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  [Export JSON] [Import JSON] [Test Tutorial]            │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (High Priority)
1. ✅ MethodRegistry with API integration
2. ✅ CommandParserEngine with /method and [negative] support
3. ✅ MethodMetadata schema
4. ✅ InputModifier for Exchange integration

### Phase 2: Enhanced Features (Medium Priority)
5. PreviewDataset for media previews
6. ConfigManager for user settings
7. CLI toolkit integration with existing graydient_exchange.py

### Phase 3: Tutorial System (High Priority)
8. TutorialEngine with highlighting
9. AnnotationPanel with media support
10. TutorialEditor GUI tool

### Phase 4: Polish (Low Priority)
11. Documentation and examples
12. Unit tests
13. Integration tests with real API

---

## File Structure

```
graydient_toolkit/
├── __init__.py
├── method_registry.py          # Dynamic method discovery
├── command_parser.py            # Telegram-style command parser
├── method_metadata.py           # Method metadata schemas
├── preview_dataset.py           # Image/video preview management
├── input_modifier.py            # Input transformation
├── config_manager.py            # User settings
├── toolkit_cli.py               # CLI interface
│
├── tutorial/                    # Tutorial system
│   ├── __init__.py
│   ├── engine.py                # TutorialEngine
│   ├── highlight_overlay.py     # Screen highlighting
│   ├── annotation_panel.py      # Annotation display
│   └── tutorial_editor.py       # Tutorial creation GUI
│
├── data/                        # Runtime data
│   ├── previews/                # Cached previews
│   ├── cache/                   # Method registry cache
│   └── tutorials/               # Tutorial definitions
│
├── examples/                    # Usage examples
│   ├── basic_usage.py
│   ├── custom_tutorial.json
│   └── advanced_config.yaml
│
└── tests/                       # Unit tests
    ├── test_method_registry.py
    ├── test_command_parser.py
    └── test_tutorial_engine.py
```

---

## Integration with Existing Code

### With graydient_exchange.py:
```python
from graydient_exchange import Exchange
from graydient_toolkit import MethodRegistry, CommandParser, InputModifier

# Initialize
exchange = Exchange(api_key="your_key")
registry = MethodRegistry(exchange)
parser = CommandParser(registry)
modifier = InputModifier(registry)

# Parse command
cmd = parser.parse("/draw a cat [blurry] --seed 42")
modified = modifier.transform(cmd)

# Execute
result = exchange.run(modified.workflow, modified.params)
```

### With graydient_display.py:
```python
from graydient_display import Display
from graydient_toolkit.tutorial import TutorialEngine

# Start display
display = Display(exchange)
display.start()

# Run tutorial
tutorial = TutorialEngine(display)
tutorial.load("getting-started")
tutorial.start()
```

---

## Success Criteria

1. ✅ Can discover all workflows/concepts from API dynamically
2. ✅ Can parse `/method` and `[negative]` syntax
3. ✅ Can modify inputs before sending to Exchange
4. ✅ Can store and display preview images/videos
5. ✅ Can run interactive tutorials with highlighting
6. ✅ Can create custom tutorials via editor
7. ✅ Backward compatible with existing CLI

---

## Notes

- The toolkit should be optional - existing code works without it
- Cache aggressively to minimize API calls
- Support offline mode with cached data
- Keep tutorial media external (don't bundle large files)
- Follow existing code style from set1-api and set2-cli
