"""
Graydient Exchange - HTTP Client Example
========================================

This example shows how ANY application can interact with the Graydient
Exchange via its HTTP API. No Python SDK required - just HTTP requests!

This pattern works for:
- Unity (C#)
- Unreal Engine (C++/Blueprint)
- Blender (Python)
- Maya (Python/MEL)
- Cinema 4D (Python)
- Nuke (Python)
- DaVinci Resolve (Lua/Python)
- Any custom application
"""

import requests
import time
import json
from typing import Optional, Callable, Dict, Any


class GraydientHTTPClient:
    """
    A simple HTTP client for the Graydient Exchange API.
    
    This client has NO dependency on the graydient SDK - it just uses
    standard HTTP requests that any language/framework can replicate.
    
    Usage:
        client = GraydientHTTPClient("http://127.0.0.1:8787")
        
        # Generate an image
        result = client.render("txt2img", {"prompt": "a cyberpunk cat"})
        print(result["image_url"])
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:8787"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the Exchange is running."""
        response = self.session.get(f"{self.base_url}/api/v1/health")
        response.raise_for_status()
        return response.json()
    
    def list_workflows(self) -> list:
        """List registered workflows."""
        response = self.session.get(f"{self.base_url}/api/v1/workflows")
        response.raise_for_status()
        return response.json().get("workflows", [])
    
    def list_graydient_workflows(self) -> list:
        """List available Graydient workflows."""
        response = self.session.get(f"{self.base_url}/api/v1/graydient/workflows")
        response.raise_for_status()
        return response.json().get("workflows", [])
    
    def search_concepts(self, query: str) -> list:
        """Search Graydient concepts."""
        response = self.session.get(
            f"{self.base_url}/api/v1/graydient/concepts",
            params={"q": query}
        )
        response.raise_for_status()
        return response.json().get("concepts", [])
    
    def submit_render(self, workflow: str, input_data: dict) -> str:
        """
        Submit a render job.
        
        Returns:
            Job ID to poll for results
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/render",
            json={"workflow": workflow, "input": input_data}
        )
        response.raise_for_status()
        return response.json()["job_id"]
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job status and result."""
        response = self.session.get(f"{self.base_url}/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return response.json()
    
    def list_jobs(self) -> list:
        """List recent jobs."""
        response = self.session.get(f"{self.base_url}/api/v1/jobs")
        response.raise_for_status()
        return response.json().get("jobs", [])
    
    def render(
        self,
        workflow: str,
        input_data: dict,
        on_progress: Optional[Callable[[float], None]] = None,
        timeout: float = 300,
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Submit render and wait for completion.
        
        Args:
            workflow: Registered workflow name
            input_data: Input parameters
            on_progress: Callback(progress_pct) for progress updates
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status checks
            
        Returns:
            Result dict with image_url, video_url, etc.
            
        Raises:
            TimeoutError: If render takes longer than timeout
            RuntimeError: If render fails
        """
        job_id = self.submit_render(workflow, input_data)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            job = self.get_job(job_id)
            
            if on_progress and job.get("progress_pct"):
                on_progress(job["progress_pct"])
            
            if job["status"] == "done":
                return job.get("result", {})
            elif job["status"] == "error":
                raise RuntimeError(f"Render failed: {job.get('error_message', 'Unknown error')}")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Render timed out after {timeout} seconds")


def example_basic_generation():
    """Example: Generate an image from text."""
    client = GraydientHTTPClient()
    
    # Check connection
    health = client.health_check()
    print(f"Exchange status: {health}")
    
    # List workflows
    workflows = client.list_workflows()
    print(f"\nAvailable workflows:")
    for wf in workflows:
        print(f"  - {wf['name']}: {wf.get('description', 'No description')}")
    
    # Generate image
    print("\nGenerating image...")
    result = client.render(
        "txt2img",
        {"prompt": "a cyberpunk cat with neon lights"},
        on_progress=lambda p: print(f"  Progress: {p:.0f}%")
    )
    
    print(f"\nGenerated image: {result.get('image_url')}")
    return result


def example_image_to_image():
    """Example: Transform an existing image."""
    client = GraydientHTTPClient()
    
    # You need a publicly accessible image URL
    image_url = "https://example.com/my-image.png"
    
    result = client.render(
        "img2img",
        {
            "prompt": "convert to oil painting style",
            "source_image": image_url,
            "strength": 0.7
        },
        on_progress=lambda p: print(f"Progress: {p:.0f}%")
    )
    
    print(f"Transformed image: {result.get('image_url')}")
    return result


def example_animation():
    """Example: Animate a still image."""
    client = GraydientHTTPClient()
    
    image_url = "https://example.com/character.png"
    
    result = client.render(
        "animate",
        {
            "motion_prompt": "character waves hello with a smile",
            "still_image": image_url
        },
        on_progress=lambda p: print(f"Progress: {p:.0f}%")
    )
    
    print(f"Animation video: {result.get('video_url')}")
    return result


def example_batch_generation():
    """Example: Generate multiple images."""
    client = GraydientHTTPClient()
    
    prompts = [
        "a red apple on a wooden table",
        "a green pear in a bowl",
        "a bunch of purple grapes",
    ]
    
    results = []
    for i, prompt in enumerate(prompts):
        print(f"\nGenerating {i+1}/{len(prompts)}: {prompt}")
        result = client.render(
            "txt2img",
            {"prompt": prompt},
            on_progress=lambda p: print(f"  Progress: {p:.0f}%")
        )
        results.append(result)
        print(f"  Result: {result.get('image_url')}")
    
    return results


def example_async_with_polling():
    """Example: Submit and poll manually for more control."""
    client = GraydientHTTPClient()
    
    # Submit job
    job_id = client.submit_render("txt2img", {"prompt": "a futuristic city"})
    print(f"Job submitted: {job_id}")
    
    # Poll manually
    while True:
        job = client.get_job(job_id)
        print(f"Status: {job['status']}, Progress: {job.get('progress_pct', 0):.0f}%")
        
        if job["status"] in ("done", "error"):
            break
        
        time.sleep(2)
    
    if job["status"] == "done":
        print(f"Result: {job['result']}")
    else:
        print(f"Error: {job.get('error_message')}")
    
    return job


def example_concept_search():
    """Example: Search for LoRA concepts."""
    client = GraydientHTTPClient()
    
    concepts = client.search_concepts("cyberpunk")
    print(f"Found {len(concepts)} concepts:")
    for c in concepts[:5]:
        print(f"  - {c['name']} ({c['type']}): {c.get('description', 'No description')}")
    
    return concepts


if __name__ == "__main__":
    print("Graydient Exchange HTTP Client Examples")
    print("=" * 50)
    
    # Run examples
    try:
        example_basic_generation()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure the bridge is running:")
        print("  python generic_bridge.py")
