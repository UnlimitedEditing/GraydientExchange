# Graydient Exchange - External App Integrations

This folder contains integration examples for connecting external applications to the Graydient Exchange.

## Quick Start

1. **Start the Python Bridge** (choose one):
   ```bash
   # For Premiere Pro
   python premiere_python_bridge.py
   
   # For After Effects
   python after_effects_python_bridge.py
   
   # For generic use
   python generic_bridge.py
   ```

2. **Run the Script** in your application:
   - Premiere Pro: File > Scripts > Run Script File > `premiere_pro_bridge.jsx`
   - After Effects: File > Scripts > Run Script File > `after_effects_bridge.jsx`

3. **The HTTP API** is now available at `http://127.0.0.1:8787`

## Available Integrations

### Adobe Premiere Pro
- **File**: `premiere_pro_bridge.jsx`
- **Features**:
  - Generate AI images from text prompts
  - Enhance/style transfer existing footage
  - Animate still images
  - Automatic import to timeline

### Adobe After Effects
- **File**: `after_effects_bridge.jsx`
- **Features**:
  - Generate images as footage layers
  - Animate images to video layers
  - Batch generate image sequences
  - Style transfer on footage

### Generic HTTP Client
Any application that can make HTTP requests can use the API:

```bash
# Submit a render
curl -X POST http://127.0.0.1:8787/api/v1/render \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "txt2img",
    "input": {"prompt": "a cyberpunk cat"}
  }'

# Check job status
curl http://127.0.0.1:8787/api/v1/jobs/{job_id}

# List available workflows
curl http://127.0.0.1:8787/api/v1/workflows
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/workflows` | GET | List registered workflows |
| `/api/v1/render` | POST | Submit a render job |
| `/api/v1/jobs` | GET | List recent jobs |
| `/api/v1/jobs/{id}` | GET | Get job status |
| `/api/v1/graydient/workflows` | GET | List Graydient workflows |
| `/api/v1/graydient/concepts` | GET | Search concepts |

## Creating Custom Integrations

### Unity Example (C#)

```csharp
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;

public class GraydientClient : MonoBehaviour
{
    private const string API_URL = "http://127.0.0.1:8787";
    
    public void GenerateImage(string prompt, System.Action<Texture2D> callback)
    {
        StartCoroutine(RenderCoroutine(prompt, callback));
    }
    
    private IEnumerator RenderCoroutine(string prompt, System.Action<Texture2D> callback)
    {
        // Submit render
        var request = new { workflow = "txt2img", input = new { prompt } };
        string json = JsonUtility.ToJson(request);
        
        using (UnityWebRequest www = UnityWebRequest.Post(
            $"{API_URL}/api/v1/render", json, "application/json"))
        {
            yield return www.SendWebRequest();
            var response = JsonUtility.FromJson<RenderResponse>(www.downloadHandler.text);
            
            // Poll for result
            yield return PollForResult(response.job_id, callback);
        }
    }
}
```

### Unreal Engine Example (Blueprint + C++)

See `unreal_example/` folder for full implementation.

### Blender Addon (Python)

See `blender_addon.py` for a complete Blender integration example.

## Troubleshooting

### "Connection refused"
- Make sure the Python bridge is running
- Check that port 8787 is not blocked by firewall
- Try changing the port in the bridge script

### "Workflow not registered"
- The workflow must be registered in the Python bridge
- Check available workflows with `curl http://127.0.0.1:8787/api/v1/workflows`

### "File not found" errors
- Ensure the file server is running on port 8788
- Check that temp directory has write permissions

## Support

For issues with the Graydient Exchange, contact: support@graydient.ai
