/**
 * Graydient Exchange - Adobe Premiere Pro Bridge
 * =================================================
 * 
 * This ExtendScript (JavaScript) panel for Premiere Pro connects to the
 * Graydient Exchange HTTP API to enable AI-powered frame generation and
 * enhancement directly from within Premiere.
 * 
 * SETUP:
 * 1. Run the Python bridge: python premiere_python_bridge.py
 * 2. In Premiere: Window > Extensions > Graydient Exchange
 * 3. Or run from Scripts panel: File > Scripts > Run Script File
 * 
 * FEATURES:
 * - Generate AI images from text prompts
 * - Enhance/transfer style of existing footage
 * - Animate still images
 * - Automatic import of results to timeline
 */

#target premiere

// Configuration
var CONFIG = {
    API_URL: "http://127.0.0.1:8787",
    FILE_SERVER_URL: "http://127.0.0.1:8788",
    POLL_INTERVAL: 2000,  // ms between status checks
    DEFAULT_DURATION: 5,  // seconds for generated clips
    TEMP_DIR: Folder.temp.fsName + "/graydient_premiere/"
};

// Ensure temp directory exists
var tempFolder = new Folder(CONFIG.TEMP_DIR);
if (!tempFolder.exists) {
    tempFolder.create();
}

/**
 * Utility: Make HTTP GET request
 */
function httpGet(url) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, false);
    xhr.send();
    
    if (xhr.status === 200) {
        return JSON.parse(xhr.responseText);
    }
    throw new Error("HTTP " + xhr.status + ": " + xhr.responseText);
}

/**
 * Utility: Make HTTP POST request
 */
function httpPost(url, data) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify(data));
    
    if (xhr.status === 200 || xhr.status === 201 || xhr.status === 202) {
        return JSON.parse(xhr.responseText);
    }
    throw new Error("HTTP " + xhr.status + ": " + xhr.responseText);
}

/**
 * Export current frame to temp directory
 */
function exportCurrentFrame() {
    var seq = app.project.activeSequence;
    if (!seq) {
        alert("No active sequence!");
        return null;
    }
    
    var playerPos = seq.getPlayerPosition();
    var timecode = playerPos.ticks;
    
    // Export frame
    var outputPath = CONFIG.TEMP_DIR + "frame_" + timecode + ".png";
    seq.exportFramePNG(playerPos, outputPath);
    
    // Wait for file to exist
    var file = new File(outputPath);
    var attempts = 0;
    while (!file.exists && attempts < 50) {
        $.sleep(100);
        attempts++;
    }
    
    if (file.exists) {
        return CONFIG.FILE_SERVER_URL + "/frame_" + timecode + ".png";
    }
    return null;
}

/**
 * Export clip frame at specific time
 */
function exportClipFrame(clip, time) {
    var seq = app.project.activeSequence;
    var outputPath = CONFIG.TEMP_DIR + "clip_frame_" + clip.name + "_" + time + ".png";
    seq.exportFramePNG(time, outputPath);
    
    var file = new File(outputPath);
    var attempts = 0;
    while (!file.exists && attempts < 50) {
        $.sleep(100);
        attempts++;
    }
    
    if (file.exists) {
        return CONFIG.FILE_SERVER_URL + "/" + file.name;
    }
    return null;
}

/**
 * Download image from URL to temp directory
 */
function downloadImage(url, filename) {
    var outputPath = CONFIG.TEMP_DIR + filename;
    
    // Use system curl to download
    var cmd = 'curl -L -o "' + outputPath + '" "' + url + '"';
    system.callSystem(cmd);
    
    var file = new File(outputPath);
    if (file.exists) {
        return outputPath;
    }
    return null;
}

/**
 * Import media file to project and add to timeline
 */
function importToTimeline(filePath, insertTime, duration) {
    var file = new File(filePath);
    if (!file.exists) {
        alert("File not found: " + filePath);
        return null;
    }
    
    // Import to project
    var importOptions = new ImportOptions(file);
    var footage = app.project.importFile(importOptions);
    
    // Add to active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert("No active sequence!");
        return null;
    }
    
    var videoTrack = seq.videoTracks[0];
    var clip = videoTrack.insertClip(footage, insertTime);
    
    // Set duration
    if (duration) {
        clip.outPoint = clip.inPoint + duration;
    }
    
    return clip;
}

/**
 * Submit render job to Graydient Exchange
 */
function submitRender(workflow, input) {
    try {
        var response = httpPost(CONFIG.API_URL + "/api/v1/render", {
            workflow: workflow,
            input: input
        });
        return response.job_id;
    } catch (e) {
        alert("Failed to submit render: " + e.message);
        return null;
    }
}

/**
 * Poll for job completion
 */
function pollJob(jobId, progressCallback) {
    var result = null;
    var maxAttempts = 150;  // 5 minutes max
    var attempts = 0;
    
    while (attempts < maxAttempts) {
        try {
            result = httpGet(CONFIG.API_URL + "/api/v1/jobs/" + jobId);
            
            if (progressCallback) {
                progressCallback(result);
            }
            
            if (result.status === "done" || result.status === "error") {
                break;
            }
        } catch (e) {
            $.writeln("Poll error: " + e.message);
        }
        
        $.sleep(CONFIG.POLL_INTERVAL);
        attempts++;
    }
    
    return result;
}

/**
 * Generate image from text prompt
 */
function generateImage(prompt, options) {
    options = options || {};
    
    var jobId = submitRender("txt2img", { prompt: prompt });
    if (!jobId) return null;
    
    // Show progress window
    var progressWin = new Window("palette", "Generating...", undefined);
    progressWin.orientation = "column";
    progressWin.add("statictext", undefined, "Generating image...");
    var progressBar = progressWin.add("progressbar", undefined, 0, 100);
    progressBar.size = [250, 20];
    var statusText = progressWin.add("statictext", undefined, "Starting...");
    progressWin.show();
    
    var result = pollJob(jobId, function(status) {
        if (status.progress_pct) {
            progressBar.value = status.progress_pct;
            statusText.text = "Progress: " + Math.round(status.progress_pct) + "%";
        }
    });
    
    progressWin.close();
    
    if (result.status === "done" && result.result) {
        var filename = "generated_" + jobId + ".png";
        var localPath = downloadImage(result.result.image_url, filename);
        
        if (localPath) {
            var seq = app.project.activeSequence;
            var insertTime = seq ? seq.getPlayerPosition() : new Time();
            return importToTimeline(localPath, insertTime, options.duration || CONFIG.DEFAULT_DURATION);
        }
    } else {
        alert("Generation failed: " + (result.error_message || "Unknown error"));
    }
    
    return null;
}

/**
 * Enhance existing footage with AI
 */
function enhanceFootage(prompt, options) {
    options = options || {};
    
    // Export current frame
    var frameUrl = exportCurrentFrame();
    if (!frameUrl) {
        alert("Failed to export frame!");
        return null;
    }
    
    var jobId = submitRender("img2img", {
        prompt: prompt,
        source_image: frameUrl
    });
    
    if (!jobId) return null;
    
    // Show progress
    var progressWin = new Window("palette", "Enhancing...", undefined);
    progressWin.orientation = "column";
    progressWin.add("statictext", undefined, "Enhancing footage...");
    var progressBar = progressWin.add("progressbar", undefined, 0, 100);
    progressBar.size = [250, 20];
    progressWin.show();
    
    var result = pollJob(jobId, function(status) {
        if (status.progress_pct) {
            progressBar.value = status.progress_pct;
        }
    });
    
    progressWin.close();
    
    if (result.status === "done" && result.result) {
        var filename = "enhanced_" + jobId + ".png";
        var localPath = downloadImage(result.result.image_url, filename);
        
        if (localPath) {
            var seq = app.project.activeSequence;
            var insertTime = seq ? seq.getPlayerPosition() : new Time();
            return importToTimeline(localPath, insertTime, options.duration || CONFIG.DEFAULT_DURATION);
        }
    }
    
    return null;
}

/**
 * Animate still image
 */
function animateImage(prompt, imagePath, options) {
    options = options || {};
    
    // Upload image to file server if needed
    var imageUrl = imagePath;
    if (imagePath.indexOf("http") !== 0) {
        // Copy to temp and serve
        var file = new File(imagePath);
        var destPath = CONFIG.TEMP_DIR + file.name;
        file.copy(destPath);
        imageUrl = CONFIG.FILE_SERVER_URL + "/" + file.name;
    }
    
    var jobId = submitRender("animate", {
        motion_prompt: prompt,
        still_image: imageUrl
    });
    
    if (!jobId) return null;
    
    // Show progress
    var progressWin = new Window("palette", "Animating...", undefined);
    progressWin.orientation = "column";
    progressWin.add("statictext", undefined, "Animating image...");
    var progressBar = progressWin.add("progressbar", undefined, 0, 100);
    progressBar.size = [250, 20];
    progressWin.show();
    
    var result = pollJob(jobId, function(status) {
        if (status.progress_pct) {
            progressBar.value = status.progress_pct;
        }
    });
    
    progressWin.close();
    
    if (result.status === "done" && result.result) {
        var videoUrl = result.result.video_url;
        if (videoUrl) {
            var filename = "animated_" + jobId + ".mp4";
            var localPath = downloadImage(videoUrl, filename);
            
            if (localPath) {
                var seq = app.project.activeSequence;
                var insertTime = seq ? seq.getPlayerPosition() : new Time();
                return importToTimeline(localPath, insertTime);
            }
        }
    }
    
    return null;
}

/**
 * Build the main UI panel
 */
function buildPanel() {
    var win = new Window("palette", "Graydient Exchange", undefined);
    win.orientation = "column";
    win.alignChildren = "fill";
    
    // Header
    var header = win.add("panel", undefined, "Graydient Exchange");
    header.orientation = "column";
    header.alignChildren = "fill";
    
    var statusText = header.add("statictext", undefined, "Status: Ready");
    
    // Check connection
    try {
        var health = httpGet(CONFIG.API_URL + "/api/v1/health");
        statusText.text = "Status: Connected ✓";
        statusText.graphics.foregroundColor = statusText.graphics.newPen(
            statusText.graphics.PenType.SOLID_COLOR, [0, 0.7, 0], 1
        );
    } catch (e) {
        statusText.text = "Status: Not Connected (Run Python bridge first)";
        statusText.graphics.foregroundColor = statusText.graphics.newPen(
            statusText.graphics.PenType.SOLID_COLOR, [0.8, 0, 0], 1
        );
    }
    
    // Tabs
    var tabs = win.add("tabbedpanel");
    tabs.alignChildren = "fill";
    tabs.preferredSize = [350, 400];
    
    // === Generate Tab ===
    var generateTab = tabs.add("tab", undefined, "Generate");
    generateTab.orientation = "column";
    generateTab.alignChildren = "fill";
    generateTab.margins = 10;
    
    generateTab.add("statictext", undefined, "Text to Image:");
    var promptInput = generateTab.add("edittext", undefined, "", {multiline: true});
    promptInput.size = [300, 80];
    promptInput.helpTip = "Describe the image you want to generate";
    
    generateTab.add("statictext", undefined, "Duration (seconds):");
    var durationInput = generateTab.add("edittext", undefined, "5");
    durationInput.size = [100, 20];
    
    var generateBtn = generateTab.add("button", undefined, "Generate Image");
    generateBtn.onClick = function() {
        var prompt = promptInput.text;
        if (!prompt) {
            alert("Please enter a prompt!");
            return;
        }
        
        var duration = parseFloat(durationInput.text) || 5;
        generateImage(prompt, { duration: duration });
    };
    
    // === Enhance Tab ===
    var enhanceTab = tabs.add("tab", undefined, "Enhance");
    enhanceTab.orientation = "column";
    enhanceTab.alignChildren = "fill";
    enhanceTab.margins = 10;
    
    enhanceTab.add("statictext", undefined, "Style Transfer / Enhancement:");
    enhanceTab.add("statictext", undefined, "(Exports current frame, applies AI)");
    
    var enhancePrompt = enhanceTab.add("edittext", undefined, "", {multiline: true});
    enhancePrompt.size = [300, 80];
    enhancePrompt.helpTip = "Describe how to enhance or transform the frame";
    
    enhanceTab.add("statictext", undefined, "Duration (seconds):");
    var enhanceDuration = enhanceTab.add("edittext", undefined, "5");
    enhanceDuration.size = [100, 20];
    
    var enhanceBtn = enhanceTab.add("button", undefined, "Enhance Frame");
    enhanceBtn.onClick = function() {
        var prompt = enhancePrompt.text;
        if (!prompt) {
            alert("Please enter an enhancement prompt!");
            return;
        }
        
        var duration = parseFloat(enhanceDuration.text) || 5;
        enhanceFootage(prompt, { duration: duration });
    };
    
    // === Animate Tab ===
    var animateTab = tabs.add("tab", undefined, "Animate");
    animateTab.orientation = "column";
    animateTab.alignChildren = "fill";
    animateTab.margins = 10;
    
    animateTab.add("statictext", undefined, "Image to Animation:");
    animateTab.add("statictext", undefined, "(Uses selected image or current frame)");
    
    var motionPrompt = animateTab.add("edittext", undefined, "", {multiline: true});
    motionPrompt.size = [300, 60];
    motionPrompt.helpTip = "Describe the motion/animation";
    
    var animateBtn = animateTab.add("button", undefined, "Animate");
    animateBtn.onClick = function() {
        var prompt = motionPrompt.text;
        if (!prompt) {
            alert("Please enter a motion description!");
            return;
        }
        
        // For now, use current frame
        // TODO: Add image file picker
        animateImage(prompt, null);
    };
    
    // === Settings Tab ===
    var settingsTab = tabs.add("tab", undefined, "Settings");
    settingsTab.orientation = "column";
    settingsTab.alignChildren = "fill";
    settingsTab.margins = 10;
    
    settingsTab.add("statictext", undefined, "API URL:");
    var apiUrlInput = settingsTab.add("edittext", undefined, CONFIG.API_URL);
    apiUrlInput.size = [300, 20];
    
    settingsTab.add("statictext", undefined, "File Server URL:");
    var fileServerInput = settingsTab.add("edittext", undefined, CONFIG.FILE_SERVER_URL);
    fileServerInput.size = [300, 20];
    
    var saveSettingsBtn = settingsTab.add("button", undefined, "Save Settings");
    saveSettingsBtn.onClick = function() {
        CONFIG.API_URL = apiUrlInput.text;
        CONFIG.FILE_SERVER_URL = fileServerInput.text;
        alert("Settings saved!");
    };
    
    // Footer
    win.add("statictext", undefined, "Graydient Exchange v1.0");
    
    return win;
}

// Main entry point
function main() {
    var panel = buildPanel();
    panel.show();
}

main();
