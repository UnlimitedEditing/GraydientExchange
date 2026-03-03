# Graydient Exchange Documentation

## Table of Contents

1. [Overview](#overview)
2. [Installation & Setup](#installation--setup)
3. [Authentication](#authentication)
4. [Core Concepts](#core-concepts)
5. [Basic Usage](#basic-usage)
6. [Full API Access](#full-api-access)
7. [HTTP API Server](#http-api-server)
8. [External App Integration](#external-app-integration)
   - [Premiere Pro Plugin](#premiere-pro-plugin)
   - [After Effects Script](#after-effects-script)
   - [Blender Addon](#blender-addon)
   - [Unity/Unreal Integration](#unityunreal-integration)
9. [Advanced Topics](#advanced-topics)
10. [API Reference](#api-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The **Graydient Exchange** is a local broker between your applications and the Graydient AI render API. It provides:

- **Simplified workflow registration** - Define once, use anywhere
- **Full Graydient API access** - Workflows, concepts, community renders
- **HTTP API server** - For external app integration without Python
- **Real-time job tracking** - Monitor renders from start to finish
- **Plugin-friendly architecture** - Easy integration with creative tools

```
┌─────────────────────────────────────────────────────────────────┐
│                        Graydient Exchange                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Workflow   │  │  Concepts   │  │     Community API       │ │
│  │    API      │  │    API      │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Virtual    │  │   Render    │  │    HTTP API Server      │ │
│  │  User API   │  │   Engine    │  │      (Port 8787)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
           ┌─────────────┐      ┌─────────────┐
           │   Python    │      │  External   │
           │    Apps     │      │    Apps     │
           └─────────────┘      └─────────────┘
```

---

## Installation & Setup

### Prerequisites

- Python 3.9 or higher
- Graydient API key (get from https://app.graydient.ai/account)

### Step 1: Install Dependencies

```bash
pip install pydantic python-dotenv requests sseclient-py rich
```

### Step 2: Install Graydient SDK

```bash
# Option A: Install from the .tgz file
pip install /path/to/graydient-python-v0_2.tgz

# Option B: Copy the graydient/ folder to your project directory
```

### Step 3: Set Up Authentication

Create a `.env` file in your project directory:

```bash
echo "GRAYDIENT_KEY=your_api_key_here" > .env
```

Or run the authentication wizard:

```bash
python graydient_auth.py
```

### Step 4: Verify Setup

```bash
python setup_check.py
```

---

## Authentication

The Exchange supports two authentication methods:

### 1. API Key (Required)

Your developer API key for all API calls:

```python
from graydient_auth import ensure_authenticated

# Prompts for key if not set, validates against API
state = ensure_authenticated()
print(f"Ready: {state.ready}")
```

### 2. Virtual User (Optional)

Per-user authentication for multi-user applications:

```python
from graydient_auth import prompt_virtual_user_otp

# Interactive OTP flow
vuser_id = prompt_virtual_user_otp()
print(f"Linked user: {vuser_id}")
```

---

## Core Concepts

### WorkflowDefinition

A reusable specification for a Graydient workflow:

```python
from graydient_exchange import WorkflowDefinition, InputMapping, OutputMapping

workflow = WorkflowDefinition(
    name="portrait_gen",           # Your internal name
    workflow="qwen",               # Graydient slug
    description="Generate portraits",
    input_map=InputMapping(
        prompt_key="description",   # Your app uses "description"
        negative_key="avoid",       # Your app uses "avoid"
        seed_key="random_seed",     # Your app uses "random_seed"
    ),
    output_map=OutputMapping(
        image_url_key="result_url",
        render_hash_key="id",
    ),
)
```

### InputMapping

Translates your app's input dict to Graydient parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `prompt_key` | Main prompt field | `"description"` → `prompt` |
| `negative_key` | Negative prompt field | `"avoid"` → `negative` |
| `image_key` | Init image URL | `"source_image"` → `inputs["init_image"]` |
| `seed_key` | Random seed | `"seed"` → `seed` |
| `extra_inputs` | Static inputs | `{"style": "url"}` |
| `slots` | Workflow slots | `{"steps": "30"}` |
| `extra` | Extra params | `{"guidance": 7.5}` |
| `transform` | Custom function | `fn(input) -> dict` |

### OutputMapping

Translates Graydient render to your app's result dict:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image_url_key` | Image URL field | `"image_url"` |
| `video_url_key` | Video URL field | `"video_url"` |
| `metadata_key` | Metadata field | `None` |
| `render_hash_key` | Render hash field | `None` |
| `transform` | Custom function | `None` |

---

## Basic Usage

### Simple Text-to-Image

```python
from graydient_exchange import Exchange, WorkflowDefinition, InputMapping, OutputMapping

# Create exchange
ex = Exchange()

# Register workflow
ex.register(WorkflowDefinition(
    name="txt2img",
    workflow="qwen",
    input_map=InputMapping(prompt_key="prompt"),
    output_map=OutputMapping(image_url_key="url"),
))

# Run render
result = ex.run("txt2img", {"prompt": "a cyberpunk cat"})
print(result["url"])  # Image URL
```

### Image-to-Image

```python
ex.register(WorkflowDefinition(
    name="style_transfer",
    workflow="edit-qwen",
    input_map=InputMapping(
        prompt_key="style_prompt",
        image_key="source_image",
    ),
))

result = ex.run("style_transfer", {
    "style_prompt": "convert to oil painting",
    "source_image": "https://example.com/photo.jpg",
})
```

### Animation

```python
ex.register(WorkflowDefinition(
    name="animate",
    workflow="animate-wan22",
    input_map=InputMapping(
        prompt_key="motion_description",
        image_key="still_image",
    ),
    output_map=OutputMapping(video_url_key="video"),
))

result = ex.run("animate", {
    "motion_description": "character waves hello",
    "still_image": "https://example.com/character.png",
})
print(result["video"])  # MP4 URL
```

### Async Rendering

```python
def on_complete(result):
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Done: {result['url']}")

def on_progress(event):
    if "rendering_progress" in event:
        p = event["rendering_progress"]
        print(f"Progress: {p['step']}/{p['total_steps']}")

# Fire and forget
record = ex.run_async(
    name="txt2img",
    input_data={"prompt": "a futuristic city"},
    callback=on_complete,
    on_progress=on_progress,
)

print(f"Job ID: {record.job_id}")
```

### Batch Processing

```python
prompts = [
    {"prompt": "a red apple"},
    {"prompt": "a green pear"},
    {"prompt": "a yellow banana"},
]

results = ex.run_batch(
    name="txt2img",
    inputs=prompts,
    sleep_between=2,  # Rate limiting
)

for r in results:
    print(r.get("url", r.get("error")))
```

---

## Full API Access

### Discover Workflows

```python
# List all available workflows
workflows = ex.workflows.list()
for w in workflows:
    print(f"{w['name']}: {w['description']}")
    print(f"  Supports: txt2img={w['supports_txt2img']}, img2img={w['supports_img2img']}")

# Search workflows
workflows = ex.workflows.list(search_term="animate")

# Get specific workflow
workflow = ex.workflows.get("qwen")
```

### Browse Concepts (LoRAs)

```python
# List all concepts
concepts = ex.concepts.all()
for c in concepts:
    print(f"{c['name']} ({c['type']}): {c['description']}")

# Search concepts
concepts = ex.concepts.search("cyberpunk")

# Filter by model family
sdxl_concepts = [c for c in concepts if c['model_family'] == 'SDXL']
```

### Browse Community Renders

```python
# Recent renders
renders = ex.community.renders()

# Search community
fantasy = ex.community.renders(search_term="fantasy landscape")

# Music/audio only
music = ex.community.renders(only_music=True)

for r in renders:
    print(f"{r['render_hash']}: {r['prompt'][:50]}...")
```

### Virtual User Management

```python
# Send OTP
otp = ex.virtual_user.send_otp("user@example.com")
print(f"OTP ID: {otp['otp_id']}")

# Confirm OTP (user enters code from email)
vuser = ex.virtual_user.confirm_otp(otp['otp_id'], "123456")
print(f"User ID: {vuser['id']}")

# Get user info
info = ex.virtual_user.info(vuser['id'])

# List all users
users = ex.virtual_user.all_users()
```

---

## HTTP API Server

Start the HTTP API server for external app integration:

```python
# Start server
api_url = ex.start_api_server(port=8787)
print(f"API running at {api_url}")

# Stop server
ex.stop_api_server()
```

### API Endpoints

#### Health Check
```http
GET /api/v1/health
```
```json
{"status": "ok", "exchange": "running"}
```

#### List Workflows
```http
GET /api/v1/workflows
```
```json
{
  "workflows": [
    {"name": "txt2img", "workflow": "qwen", "description": "..."}
  ]
}
```

#### Submit Render
```http
POST /api/v1/render
Content-Type: application/json

{
  "workflow": "txt2img",
  "input": {
    "prompt": "a cyberpunk cat"
  }
}
```
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Render started. Poll /api/v1/jobs/{job_id} for status."
}
```

#### Get Job Status
```http
GET /api/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "progress_pct": 100,
  "result": {
    "image_url": "https://...",
    "render_hash": "abc123"
  }
}
```

#### List Jobs
```http
GET /api/v1/jobs
```
```json
{
  "jobs": [
    {"job_id": "...", "status": "done", "progress_pct": 100}
  ]
}
```

#### Graydient Workflows
```http
GET /api/v1/graydient/workflows
```

#### Search Concepts
```http
GET /api/v1/graydient/concepts?q=cyberpunk
```

---

## External App Integration

### Premiere Pro Plugin

**ExtendScript (JavaScript for Premiere Pro):**

```javascript
// GraydientExchange.jsx
// Premiere Pro panel script

#target premiere

var GRAYDIENT_API = "http://127.0.0.1:8787";

function sendFrameToGraydient(prompt, framePath) {
    // Upload frame to temporary URL (you'll need a file hosting solution)
    var imageUrl = uploadFrame(framePath);
    
    // Submit render request
    var xhr = new XMLHttpRequest();
    xhr.open("POST", GRAYDIENT_API + "/api/v1/render", false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({
        workflow: "edit-qwen",
        input: {
            prompt: prompt,
            source_image: imageUrl
        }
    }));
    
    var response = JSON.parse(xhr.responseText);
    return response.job_id;
}

function pollForResult(jobId) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", GRAYDIENT_API + "/api/v1/jobs/" + jobId, false);
    xhr.send();
    
    var response = JSON.parse(xhr.responseText);
    return response;
}

// Example: Apply AI effect to selected clip
function applyAIEffect() {
    var seq = app.project.activeSequence;
    var clip = seq.getSelection()[0];
    
    var prompt = prompt("Enter AI prompt:", "cinematic color grading");
    if (!prompt) return;
    
    // Export frame
    var framePath = exportFrame(clip);
    
    // Submit to Graydient
    var jobId = sendFrameToGraydient(prompt, framePath);
    
    // Poll for result
    var result = null;
    while (!result || result.status !== "done") {
        $.sleep(2000);  // Wait 2 seconds
        result = pollForResult(jobId);
        
        if (result.status === "error") {
            alert("Error: " + result.error_message);
            return;
        }
        
        $.writeln("Status: " + result.status + 
                  (result.progress_pct ? " (" + result.progress_pct + "%)" : ""));
    }
    
    // Download result and import
    var imagePath = downloadImage(result.result.image_url);
    importImageToTimeline(imagePath, clip);
}

applyAIEffect();
```

**Python Bridge (run alongside Premiere):**

```python
# premiere_bridge.py
# Run this to start the Exchange and handle file operations

from graydient_exchange import Exchange, WorkflowDefinition, InputMapping
import http.server
import socketserver
import json
import os
from pathlib import Path

# Start Exchange
ex = Exchange()

# Register workflows
ex.register(WorkflowDefinition(
    name="frame_enhance",
    workflow="edit-qwen",
    input_map=InputMapping(prompt_key="prompt", image_key="frame"),
))

# Start API server
api_url = ex.start_api_server(port=8787)
print(f"Premiere bridge running at {api_url}")

# Additional file server for frame uploads
class FileHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/tmp/graydient_frames", **kwargs)

# Create frame directory
Path("/tmp/graydient_frames").mkdir(exist_ok=True)

# Start file server
file_server = socketserver.TCPServer(("127.0.0.1", 8788), FileHandler)
print("File server running at http://127.0.0.1:8788")

file_server.serve_forever()
```

### After Effects Script

**ExtendScript for After Effects:**

```javascript
// GraydientAE.jsx

#target aftereffects

var GRAYDIENT_API = "http://127.0.0.1:8787";

function generateLayerFromPrompt(prompt, duration) {
    // Submit render
    var xhr = new XMLHttpRequest();
    xhr.open("POST", GRAYDIENT_API + "/api/v1/render", false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({
        workflow: "txt2img",
        input: { prompt: prompt }
    }));
    
    var job = JSON.parse(xhr.responseText);
    
    // Poll for completion
    var result = null;
    while (!result || (result.status !== "done" && result.status !== "error")) {
        $.sleep(3000);
        
        xhr.open("GET", GRAYDIENT_API + "/api/v1/jobs/" + job.job_id, false);
        xhr.send();
        result = JSON.parse(xhr.responseText);
        
        $.writeln("Progress: " + (result.progress_pct || 0) + "%");
    }
    
    if (result.status === "error") {
        alert("Render failed: " + result.error_message);
        return null;
    }
    
    // Import image
    var importOpts = new ImportOptions(File(result.result.image_url));
    var footage = app.project.importFile(importOpts);
    
    // Add to composition
    var comp = app.project.activeItem;
    var layer = comp.layers.add(footage);
    layer.outPoint = layer.inPoint + duration;
    
    return layer;
}

// UI Panel
function buildUI() {
    var win = new Window("palette", "Graydient Exchange", undefined);
    win.orientation = "column";
    
    win.add("statictext", undefined, "Prompt:");
    var promptInput = win.add("edittext", undefined, "", {multiline: true});
    promptInput.size = [250, 60];
    
    var generateBtn = win.add("button", undefined, "Generate");
    generateBtn.onClick = function() {
        var prompt = promptInput.text;
        if (prompt) {
            generateLayerFromPrompt(prompt, 5);
        }
    };
    
    win.show();
}

buildUI();
```

### Blender Addon

```python
# graydient_blender.py
# Install as Blender addon

bl_info = {
    "name": "Graydient Exchange",
    "blender": (3, 0, 0),
    "category": "Render",
}

import bpy
import requests
import threading

GRAYDIENT_API = "http://127.0.0.1:8787"

class GRAYDIENT_OT_generate_image(bpy.types.Operator):
    bl_idname = "graydient.generate_image"
    bl_label = "Generate Image"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prompt = context.scene.graydient_prompt
        
        def render():
            # Submit render
            response = requests.post(
                f"{GRAYDIENT_API}/api/v1/render",
                json={
                    "workflow": "txt2img",
                    "input": {"prompt": prompt}
                }
            )
            job = response.json()
            
            # Poll for result
            result = None
            while not result or result["status"] not in ("done", "error"):
                import time
                time.sleep(2)
                r = requests.get(f"{GRAYDIENT_API}/api/v1/jobs/{job['job_id']}")
                result = r.json()
            
            if result["status"] == "done":
                # Download and load image
                import urllib.request
                image_path = "/tmp/graydient_result.png"
                urllib.request.urlretrieve(
                    result["result"]["image_url"], 
                    image_path
                )
                
                # Load into Blender
                bpy.ops.image.open(filepath=image_path)
                
                # Update UI
                def update():
                    self.report({'INFO'}, "Image generated!")
                bpy.app.timers.register(update)
        
        thread = threading.Thread(target=render)
        thread.start()
        
        return {'FINISHED'}

class GRAYDIENT_PT_panel(bpy.types.Panel):
    bl_label = "Graydient Exchange"
    bl_idname = "GRAYDIENT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Graydient'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.prop(scene, "graydient_prompt")
        layout.operator("graydient.generate_image")

def register():
    bpy.utils.register_class(GRAYDIENT_OT_generate_image)
    bpy.utils.register_class(GRAYDIENT_PT_panel)
    bpy.types.Scene.graydient_prompt = bpy.props.StringProperty(
        name="Prompt",
        default="a 3D render of a futuristic vehicle"
    )

def unregister():
    bpy.utils.unregister_class(GRAYDIENT_OT_generate_image)
    bpy.utils.unregister_class(GRAYDIENT_PT_panel)
    del bpy.types.Scene.graydient_prompt

if __name__ == "__main__":
    register()
```

### Unity/Unreal Integration

**Unity C# Script:**

```csharp
// GraydientExchange.cs
// Attach to a GameObject in Unity

using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

public class GraydientExchange : MonoBehaviour
{
    private const string API_URL = "http://127.0.0.1:8787";
    
    [System.Serializable]
    public class RenderRequest
    {
        public string workflow;
        public RenderInput input;
    }
    
    [System.Serializable]
    public class RenderInput
    {
        public string prompt;
    }
    
    [System.Serializable]
    public class RenderResponse
    {
        public string job_id;
        public string status;
    }
    
    [System.Serializable]
    public class JobStatus
    {
        public string job_id;
        public string status;
        public float progress_pct;
        public JobResult result;
    }
    
    [System.Serializable]
    public class JobResult
    {
        public string image_url;
    }
    
    public void GenerateImage(string prompt, Action<Texture2D> onComplete)
    {
        StartCoroutine(RenderCoroutine(prompt, onComplete));
    }
    
    private IEnumerator RenderCoroutine(string prompt, Action<Texture2D> onComplete)
    {
        // Submit render
        var request = new RenderRequest
        {
            workflow = "txt2img",
            input = new RenderInput { prompt = prompt }
        };
        
        string json = JsonUtility.ToJson(request);
        
        using (UnityWebRequest www = UnityWebRequest.Post(
            $"{API_URL}/api/v1/render", 
            json, 
            "application/json"))
        {
            yield return www.SendWebRequest();
            
            if (www.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Error: {www.error}");
                yield break;
            }
            
            var response = JsonUtility.FromJson<RenderResponse>(www.downloadHandler.text);
            Debug.Log($"Job started: {response.job_id}");
            
            // Poll for result
            yield return PollForResult(response.job_id, onComplete);
        }
    }
    
    private IEnumerator PollForResult(string jobId, Action<Texture2D> onComplete)
    {
        JobStatus status = null;
        
        do
        {
            yield return new WaitForSeconds(2);
            
            using (UnityWebRequest www = UnityWebRequest.Get($"{API_URL}/api/v1/jobs/{jobId}"))
            {
                yield return www.SendWebRequest();
                
                if (www.result == UnityWebRequest.Result.Success)
                {
                    status = JsonUtility.FromJson<JobStatus>(www.downloadHandler.text);
                    Debug.Log($"Progress: {status.progress_pct}%");
                }
            }
        } while (status == null || (status.status != "done" && status.status != "error"));
        
        if (status.status == "done" && status.result != null)
        {
            yield return DownloadImage(status.result.image_url, onComplete);
        }
    }
    
    private IEnumerator DownloadImage(string url, Action<Texture2D> onComplete)
    {
        using (UnityWebRequest www = UnityWebRequestTexture.GetTexture(url))
        {
            yield return www.SendWebRequest();
            
            if (www.result == UnityWebRequest.Result.Success)
            {
                Texture2D texture = DownloadHandlerTexture.GetContent(www);
                onComplete?.Invoke(texture);
            }
            else
            {
                Debug.LogError($"Download error: {www.error}");
            }
        }
    }
}
```

---

## Advanced Topics

### Custom Transforms

```python
# Complex prompt building
def build_prompt(inputs):
    base = inputs.get("subject", "a person")
    style = inputs.get("style", "photorealistic")
    lighting = inputs.get("lighting", "soft natural light")
    
    return {
        "prompt": f"{base}, {style}, {lighting}, highly detailed, 8k",
        "negative": "blurry, low quality, distorted",
        "guidance": 7.5,
    }

ex.register(WorkflowDefinition(
    name="custom",
    workflow="qwen",
    input_map=InputMapping(transform=build_prompt),
))
```

### Pipeline Chaining

```python
# Generate → Animate pipeline
def pipeline():
    # Step 1: Generate base image
    gen_result = ex.run("generate", {"prompt": "a knight on horseback"})
    image_url = gen_result["image_url"]
    
    # Step 2: Animate the result
    anim_result = ex.run("animate", {
        "still_image": image_url,
        "motion_prompt": "the knight raises their sword"
    })
    
    return anim_result["video_url"]
```

### Observer Pattern

```python
# Log all jobs to database
def db_logger(record):
    db.execute(
        "INSERT INTO renders (job_id, status, render_hash) VALUES (?, ?, ?)",
        (record.job_id, record.status.value, record.render_hash)
    )
    db.commit()

ex.add_observer(db_logger)

# WebSocket push
def ws_pusher(record):
    websocket.broadcast({
        "type": "render_update",
        "job": record.to_dict()
    })

ex.add_observer(ws_pusher)
```

---

## API Reference

### Exchange Class

#### Constructor
```python
Exchange(api_key: Optional[str] = None)
```

#### Properties
| Property | Type | Description |
|----------|------|-------------|
| `workflows` | `WorkflowsAPI` | Workflow discovery |
| `concepts` | `ConceptsAPI` | Concept/LoRA discovery |
| `community` | `CommunityAPI` | Community renders |
| `virtual_user` | `VirtualUserAPI` | OTP authentication |

#### Methods

##### register
```python
register(definition: WorkflowDefinition) -> Exchange
```
Register a workflow definition.

##### unregister
```python
unregister(name: str) -> Exchange
```
Remove a registered workflow.

##### list_workflows
```python
list_workflows() -> List[Dict[str, Any]]
```
List registered workflows.

##### run
```python
run(
    name: str,
    input_data: Dict[str, Any],
    on_progress: Optional[Callable[[Dict], None]] = None,
    timeout: float = 300,
    poll_interval: float = 0.05
) -> Dict[str, Any]
```
Execute a workflow synchronously.

##### run_async
```python
run_async(
    name: str,
    input_data: Dict[str, Any],
    callback: Callable[[Dict], None],
    on_progress: Optional[Callable[[Dict], None]] = None,
    timeout: float = 300
) -> JobRecord
```
Execute a workflow asynchronously.

##### run_batch
```python
run_batch(
    name: str,
    inputs: List[Dict[str, Any]],
    on_progress: Optional[Callable[[int, Dict], None]] = None,
    sleep_between: float = 0,
    timeout: float = 300
) -> List[Dict[str, Any]]
```
Execute multiple renders sequentially.

##### start_api_server
```python
start_api_server(port: int = 8787, host: str = "127.0.0.1") -> str
```
Start HTTP API server for external apps.

##### stop_api_server
```python
stop_api_server()
```
Stop the HTTP API server.

##### add_observer
```python
add_observer(callback: Callable[[JobRecord], None]) -> Exchange
```
Register a job state change observer.

##### job_history
```python
job_history(limit: int = 100) -> List[JobRecord]
```
Get recent job records.

##### get_job
```python
get_job(job_id: str) -> Optional[JobRecord]
```
Get a specific job by ID.

---

## Troubleshooting

### "Cannot import graydient"

**Cause:** SDK not installed or not in Python path.

**Solution:**
```bash
pip install /path/to/graydient-python-v0_2.tgz
```

### "No Graydient API key found"

**Cause:** GRAYDIENT_KEY not set.

**Solution:**
```bash
python graydient_auth.py
```

### "Key rejected by Graydient API"

**Cause:** Invalid API key.

**Solution:**
- Verify key at https://app.graydient.ai/account
- Check for extra spaces or characters

### "Network error"

**Cause:** Cannot reach Graydient API.

**Solution:**
- Check internet connection
- Verify firewall settings
- Try again later (may be temporary outage)

### "Rate limited"

**Cause:** Too many requests.

**Solution:**
- Add delays between requests
- Use batch processing with `sleep_between`
- Contact Graydient for rate limit increase

---

## License

This documentation and the Graydient Exchange are provided as-is for integration with the Graydient platform.

For support, contact: support@graydient.ai
