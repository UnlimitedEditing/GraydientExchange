# Graydient Toolkit for CLI

A comprehensive toolkit for modifying inputs registered by the Graydient API to a local CLI, bridging media from the Graydient SaaS platform to other applications.

## Features

- **Dynamic Method Discovery**: Automatically fetches and caches workflows and concepts from the Graydient API
- **Telegram-Style Commands**: Parse `/method` (positive) and `[negative]` handles for intuitive input
- **Method Metadata**: Rich descriptions, parameters, and capabilities for each method
- **Preview Dataset**: Manage image and video previews for workflows and concepts
- **Input Transformation**: Transform parsed commands into Exchange-compatible format
- **Configuration Management**: User preferences, method aliases, and default settings
- **Interactive Tutorial System**: Step-by-step onboarding with screen highlighting and rich annotations
- **Tutorial Editor**: GUI tool for creating custom tutorials

## Installation

```bash
# Clone or copy the toolkit to your project
cp -r graydient_toolkit /path/to/your/project/

# Or install alongside graydient_exchange
pip install -e .
```

## Quick Start

```python
from graydient_exchange import Exchange
from graydient_toolkit import (
    MethodRegistry,
    CommandParserEngine,
    InputModifier,
)

# Initialize
exchange = Exchange(api_key="your_key")
registry = MethodRegistry(exchange)
parser = CommandParserEngine(registry)
modifier = InputModifier(registry)

# Parse a Telegram-style command
parsed = parser.parse("/draw a cyberpunk cat [blurry, low quality] --seed 42")

# Transform for Exchange
result = modifier.transform(parsed)

# Execute
output = exchange.run(result.workflow, result.params)
print(output["image_url"])
```

## Command Syntax

### Telegram-Style Commands (Recommended)

```
/draw <prompt> [negative prompts] [--parameters]
```

**Examples:**
```bash
# Simple generation
/draw a beautiful landscape

# With seed for reproducibility
/draw a cyberpunk cat --seed 42

# With negative prompts
/draw a portrait [blurry, distorted, ugly]

# Full example
/draw a majestic eagle --seed 123 --guidance 8.0 --width 1024 --height 768
```

### Positive Handles (/methods)

Commands that specify what workflow to use:

| Command | Workflow | Description |
|---------|----------|-------------|
| `/draw` or `/d` | `qwen` | Generate images from text |
| `/animate` or `/a` | `animate-wan22` | Animate still images |
| `/style` or `/s` | `edit-qwen` | Apply style transfer |
| `/upscale` or `/u` | `upscale` | Upscale images |
| `/img2img` or `/i2i` | `edit-qwen` | Image-to-image transformation |

### Negative Handles ([negatives])

Specify what to avoid in generation:

```
[blurry, low quality, distorted]
[nsfw, violence, gore]
[watermark, signature, text]
```

Multiple negative blocks can be combined:
```
/draw a cat [blurry] [low quality] [distorted]
```

### Legacy Syntax (--flags)

For backward compatibility:

```bash
--prompt="a cat" --seed=42 --guidance=7.5
--negative="blurry, low quality"
```

## CLI Usage

```bash
# Refresh and list all methods
python -m graydient_toolkit.toolkit_cli registry --refresh --list

# Parse a command
python -m graydient_toolkit.toolkit_cli parse "/draw a cat --seed 42"

# Show configuration
python -m graydient_toolkit.toolkit_cli config --show

# Add a method alias
python -m graydient_toolkit.toolkit_cli config --alias p portrait

# Launch tutorial editor
python -m graydient_toolkit.toolkit_cli tutorial --edit

# List tutorials
python -m graydient_toolkit.toolkit_cli tutorial --list

# Run a tutorial
python -m graydient_toolkit.toolkit_cli tutorial --run getting-started
```

## Module Overview

### `method_registry.py`

Dynamic discovery and caching of workflows and concepts.

```python
from graydient_toolkit import MethodRegistry, CachePolicy

# Create registry with custom cache policy
cache_policy = CachePolicy(
    ttl_seconds=3600,  # 1 hour
    persist_to_disk=True,
)
registry = MethodRegistry(exchange, cache_policy=cache_policy)

# Refresh from API
registry.refresh()

# Search workflows
workflows = registry.search_workflows("portrait")

# Get method metadata
method = registry.get_workflow("qwen")
print(method.description)
print(method.parameters)
```

### `command_parser.py`

Parse Telegram-style commands.

```python
from graydient_toolkit import CommandParserEngine, quick_parse

# With registry (for validation)
parser = CommandParserEngine(registry)
parsed = parser.parse("/draw a cat --seed 42")

# Without registry (basic parsing)
parsed = quick_parse("/draw a cat --seed 42")

print(parsed.workflow)      # "qwen"
print(parsed.prompt)        # "a cat"
print(parsed.parameters)    # {"seed": 42}
```

### `input_modifier.py`

Transform parsed commands for Exchange.

```python
from graydient_toolkit import InputModifier, apply_aspect_ratio

modifier = InputModifier(registry)

# Add custom modifiers
modifier.add_modifier(apply_aspect_ratio("16:9"))

# Transform
result = modifier.transform(parsed)
print(result.to_exchange_format())
```

### `config_manager.py`

Manage user preferences.

```python
from graydient_toolkit import ConfigManager, InputStyle

config = ConfigManager()

# Set preferences
config.set("input_style", InputStyle.TELEGRAM)
config.set_default("seed", 42)
config.add_alias("p", "portrait")

# Save
config.save()
```

### `preview_dataset.py`

Manage preview images and videos.

```python
from graydient_toolkit import PreviewDataset

previews = PreviewDataset()

# Download preview
previews.download(
    method_slug="qwen",
    category="workflow",
    url="https://example.com/preview.jpg"
)

# Get previews for method
qwen_previews = previews.get_previews("qwen", "workflow")
```

### `tutorial/` - Tutorial System

Interactive onboarding with screen highlighting.

```python
from graydient_toolkit.tutorial import TutorialEngine, TutorialDefinition

# Load and run a tutorial
engine = TutorialEngine()
engine.load_tutorial("getting-started")
engine.start()

# Navigate steps
engine.next_step()
engine.previous_step()

# Get current step info
step = engine.current_step
print(step.title)
print(step.text)
```

#### Tutorial Editor

```python
from graydient_toolkit.tutorial import TutorialEditor

# Launch GUI editor
editor = TutorialEditor()
editor.run()
```

## Tutorial Definition Format

```json
{
  "id": "my-tutorial",
  "title": "My Tutorial",
  "description": "Learn how to...",
  "difficulty": "beginner",
  "estimated_duration_minutes": 5,
  "steps": [
    {
      "id": "step-1",
      "title": "Welcome",
      "text": "Welcome to the tutorial!",
      "highlight": {
        "x": 10,
        "y": 20,
        "width": 80,
        "height": 15,
        "use_percent": true,
        "shape": "rectangle",
        "color": "#00ff41"
      },
      "media": {
        "media_type": "image",
        "src": "path/to/image.png",
        "caption": "Example image"
      },
      "trigger": "MANUAL",
      "skippable": true
    }
  ]
}
```

## Configuration File

Located at `~/.graydient_toolkit/config.json`:

```json
{
  "input_style": "mixed",
  "method_aliases": {
    "p": "portrait",
    "l": "landscape"
  },
  "defaults": {
    "seed": null,
    "guidance": 7.5,
    "steps": 30,
    "width": 1024,
    "height": 1024
  },
  "display_theme": "phosphor",
  "viewer_port": 7788,
  "cache_ttl_seconds": 3600
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GRAYDIENT CLI TOOLKIT                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Method     │◄───│  Graydient   │    │   Preview    │      │
│  │   Registry   │    │     API      │    │   Dataset    │      │
│  └──────┬───────┘    └──────────────┘    └──────────────┘      │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              CommandParserEngine                          │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────────────────┐   │   │
│  │  │ /method │  │[negative│  │    --legacy-flag        │   │   │
│  │  │(positive│  │ handles]│  │                         │   │   │
│  │  └─────────┘  └─────────┘  └─────────────────────────┘   │   │
│  └────────────────────────┬──────────────────────────────────┘   │
│                           │                                       │
│           ┌───────────────┼───────────────┐                      │
│           ▼               ▼               ▼                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Input     │  │   Method    │  │   Config    │              │
│  │  Modifier   │  │  Validator  │  │   Manager   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                    INTERACTIVE TUTORIAL SYSTEM                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Tutorial   │  │   Highlight  │  │  Annotation  │          │
│  │    Engine    │  │   Overlay    │  │    Panel     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    TutorialEditor                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Examples

See the `examples/` directory:

- `basic_usage.py` - Core functionality demonstration
- `getting_started_tutorial.json` - Sample tutorial definition

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please follow the existing code style and add tests for new features.

## Support

For issues and questions:
- GitHub Issues: [your-repo]/issues
- Documentation: https://graydient.ai/docs
