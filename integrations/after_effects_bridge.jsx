/**
 * Graydient Exchange - Adobe After Effects Bridge
 * ================================================
 * 
 * This ExtendScript for After Effects connects to the Graydient Exchange
 * HTTP API to enable AI-powered image generation and animation directly
 * from within After Effects.
 * 
 * SETUP:
 * 1. Run the Python bridge: python after_effects_python_bridge.py
 * 2. In After Effects: File > Scripts > Run Script File
 * 3. Or install in ScriptUI Panels folder for dockable panel
 * 
 * FEATURES:
 * - Generate AI images as footage layers
 * - Animate still images to video layers
 * - Batch generate image sequences
 * - Style transfer on existing footage
 */

#target aftereffects

// Configuration
var CONFIG = {
    API_URL: "http://127.0.0.1:8787",
    FILE_SERVER_URL: "http://127.0.0.1:8788",
    POLL_INTERVAL: 2000,
    TEMP_DIR: Folder.temp.fsName + "/graydient_ae/"
};

// Ensure temp directory exists
var tempFolder = new Folder(CONFIG.TEMP_DIR);
if (!tempFolder.exists) {
    tempFolder.create();
}

/**
 * HTTP GET request
 */
function httpGet(url) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, false);
    xhr.send();
    if (xhr.status === 200) {
        return JSON.parse(xhr.responseText);
    }
    throw new Error("HTTP " + xhr.status);
}

/**
 * HTTP POST request
 */
function httpPost(url, data) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify(data));
    if (xhr.status >= 200 && xhr.status < 300) {
        return JSON.parse(xhr.responseText);
    }
    throw new Error("HTTP " + xhr.status + ": " + xhr.responseText);
}

/**
 * Download file using curl
 */
function downloadFile(url, filename) {
    var outputPath = CONFIG.TEMP_DIR + filename;
    var cmd = 'curl -L -o "' + outputPath + '" "' + url + '"';
    system.callSystem(cmd);
    
    var file = new File(outputPath);
    return file.exists ? outputPath : null;
}

/**
 * Import footage to project
 */
function importFootage(filePath) {
    var file = new File(filePath);
    if (!file.exists) {
        alert("File not found: " + filePath);
        return null;
    }
    
    var importOpts = new ImportOptions(file);
    return app.project.importFile(importOpts);
}

/**
 * Add footage to active composition
 */
function addToComposition(footage, startTime, duration) {
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem)) {
        alert("No active composition!");
        return null;
    }
    
    var layer = comp.layers.add(footage);
    
    if (startTime !== undefined) {
        layer.startTime = startTime;
    }
    
    if (duration !== undefined) {
        layer.outPoint = layer.inPoint + duration;
    }
    
    return layer;
}

/**
 * Poll job until complete
 */
function pollJob(jobId, onProgress) {
    var result = null;
    var maxAttempts = 150;
    
    for (var i = 0; i < maxAttempts; i++) {
        try {
            result = httpGet(CONFIG.API_URL + "/api/v1/jobs/" + jobId);
            
            if (onProgress) {
                onProgress(result);
            }
            
            if (result.status === "done" || result.status === "error") {
                break;
            }
        } catch (e) {
            $.writeln("Poll error: " + e.message);
        }
        
        $.sleep(CONFIG.POLL_INTERVAL);
    }
    
    return result;
}

/**
 * Generate image from prompt
 */
function generateImage(prompt, options) {
    options = options || {};
    
    app.beginUndoGroup("Graydient Generate Image");
    
    try {
        // Submit render
        var response = httpPost(CONFIG.API_URL + "/api/v1/render", {
            workflow: "txt2img",
            input: { prompt: prompt }
        });
        
        // Show progress dialog
        var progressWin = new Window("palette", "Generating...");
        progressWin.orientation = "column";
        progressWin.add("statictext", undefined, "Generating image with AI...");
        var progressBar = progressWin.add("progressbar", undefined, 0, 100);
        progressBar.size = [250, 20];
        var statusText = progressWin.add("statictext", undefined, "Starting...");
        progressWin.show();
        
        // Poll for result
        var result = pollJob(response.job_id, function(status) {
            if (status.progress_pct) {
                progressBar.value = status.progress_pct;
                statusText.text = "Progress: " + Math.round(status.progress_pct) + "%";
            }
        });
        
        progressWin.close();
        
        if (result.status === "done" && result.result) {
            var filename = "gen_" + response.job_id + ".png";
            var localPath = downloadFile(result.result.image_url, filename);
            
            if (localPath) {
                var footage = importFootage(localPath);
                if (footage) {
                    var layer = addToComposition(
                        footage, 
                        options.startTime || 0,
                        options.duration || 5
                    );
                    
                    // Center in composition
                    var comp = app.project.activeItem;
                    layer.position.setValue([comp.width / 2, comp.height / 2]);
                    
                    alert("Image generated and added to composition!");
                    return layer;
                }
            }
        } else {
            alert("Generation failed: " + (result.error_message || "Unknown error"));
        }
    } catch (e) {
        alert("Error: " + e.message);
    } finally {
        app.endUndoGroup();
    }
    
    return null;
}

/**
 * Animate still image
 */
function animateImage(imagePath, motionPrompt, options) {
    options = options || {};
    
    app.beginUndoGroup("Graydient Animate Image");
    
    try {
        // Handle image path
        var imageUrl = imagePath;
        if (imagePath.indexOf("http") !== 0) {
            // Copy to temp and serve
            var file = new File(imagePath);
            var destPath = CONFIG.TEMP_DIR + file.name;
            file.copy(destPath);
            imageUrl = CONFIG.FILE_SERVER_URL + "/" + file.name;
        }
        
        // Submit render
        var response = httpPost(CONFIG.API_URL + "/api/v1/render", {
            workflow: "animate",
            input: {
                motion_prompt: motionPrompt,
                still_image: imageUrl
            }
        });
        
        // Show progress
        var progressWin = new Window("palette", "Animating...");
        progressWin.orientation = "column";
        progressWin.add("statictext", undefined, "Animating image with AI...");
        var progressBar = progressWin.add("progressbar", undefined, 0, 100);
        progressBar.size = [250, 20];
        progressWin.show();
        
        var result = pollJob(response.job_id, function(status) {
            if (status.progress_pct) {
                progressBar.value = status.progress_pct;
            }
        });
        
        progressWin.close();
        
        if (result.status === "done" && result.result && result.result.video_url) {
            var filename = "anim_" + response.job_id + ".mp4";
            var localPath = downloadFile(result.result.video_url, filename);
            
            if (localPath) {
                var footage = importFootage(localPath);
                if (footage) {
                    var layer = addToComposition(footage, options.startTime || 0);
                    alert("Animation created and added to composition!");
                    return layer;
                }
            }
        } else {
            alert("Animation failed: " + (result.error_message || "Unknown error"));
        }
    } catch (e) {
        alert("Error: " + e.message);
    } finally {
        app.endUndoGroup();
    }
    
    return null;
}

/**
 * Batch generate image sequence
 */
function batchGenerate(prompts, options) {
    options = options || {};
    
    app.beginUndoGroup("Graydient Batch Generate");
    
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem)) {
        alert("No active composition!");
        return;
    }
    
    var progressWin = new Window("palette", "Batch Generating...");
    progressWin.orientation = "column";
    var statusText = progressWin.add("statictext", undefined, "Processing 0/" + prompts.length);
    var progressBar = progressWin.add("progressbar", undefined, 0, prompts.length);
    progressBar.size = [250, 20];
    progressWin.show();
    
    var layers = [];
    var startTime = options.startTime || 0;
    var duration = options.duration || 2;
    
    for (var i = 0; i < prompts.length; i++) {
        statusText.text = "Processing " + (i + 1) + "/" + prompts.length;
        progressBar.value = i;
        
        try {
            var response = httpPost(CONFIG.API_URL + "/api/v1/render", {
                workflow: "txt2img",
                input: { prompt: prompts[i] }
            });
            
            var result = pollJob(response.job_id);
            
            if (result.status === "done" && result.result) {
                var filename = "batch_" + i + "_" + response.job_id + ".png";
                var localPath = downloadFile(result.result.image_url, filename);
                
                if (localPath) {
                    var footage = importFootage(localPath);
                    if (footage) {
                        var layer = addToComposition(footage, startTime + (i * duration), duration);
                        layers.push(layer);
                    }
                }
            }
        } catch (e) {
            $.writeln("Batch item " + i + " failed: " + e.message);
        }
    }
    
    progressWin.close();
    alert("Batch complete! Generated " + layers.length + " images.");
    
    app.endUndoGroup();
    return layers;
}

/**
 * Style transfer on selected layer
 */
function styleTransfer(stylePrompt, options) {
    options = options || {};
    
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem)) {
        alert("No active composition!");
        return null;
    }
    
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {
        alert("Please select a layer!");
        return null;
    }
    
    var layer = selectedLayers[0];
    
    app.beginUndoGroup("Graydient Style Transfer");
    
    try {
        // Export frame (simplified - in production, render the layer)
        // For now, we'll need the user to provide an image path
        var imagePath = options.imagePath;
        if (!imagePath) {
            alert("Please provide an image path in options!");
            return null;
        }
        
        var file = new File(imagePath);
        var destPath = CONFIG.TEMP_DIR + file.name;
        file.copy(destPath);
        var imageUrl = CONFIG.FILE_SERVER_URL + "/" + file.name;
        
        // Submit render
        var response = httpPost(CONFIG.API_URL + "/api/v1/render", {
            workflow: "img2img",
            input: {
                prompt: stylePrompt,
                source_image: imageUrl
            }
        });
        
        var progressWin = new Window("palette", "Transferring Style...");
        progressWin.orientation = "column";
        progressWin.add("statictext", undefined, "Applying style transfer...");
        var progressBar = progressWin.add("progressbar", undefined, 0, 100);
        progressBar.size = [250, 20];
        progressWin.show();
        
        var result = pollJob(response.job_id, function(status) {
            if (status.progress_pct) {
                progressBar.value = status.progress_pct;
            }
        });
        
        progressWin.close();
        
        if (result.status === "done" && result.result) {
            var filename = "styled_" + response.job_id + ".png";
            var localPath = downloadFile(result.result.image_url, filename);
            
            if (localPath) {
                var footage = importFootage(localPath);
                if (footage) {
                    var newLayer = addToComposition(
                        footage,
                        layer.inPoint,
                        layer.outPoint - layer.inPoint
                    );
                    alert("Style transfer complete!");
                    return newLayer;
                }
            }
        }
    } catch (e) {
        alert("Error: " + e.message);
    } finally {
        app.endUndoGroup();
    }
    
    return null;
}

/**
 * Build the UI panel
 */
function buildPanel() {
    var win = (this instanceof Panel) ? this : new Window("palette", "Graydient Exchange", undefined);
    win.orientation = "column";
    win.alignChildren = "fill";
    
    // Header
    var header = win.add("panel", undefined, "Graydient Exchange for After Effects");
    header.orientation = "column";
    header.alignChildren = "fill";
    
    var statusText = header.add("statictext", undefined, "Checking connection...");
    
    // Check connection
    try {
        var health = httpGet(CONFIG.API_URL + "/api/v1/health");
        statusText.text = "✓ Connected to Graydient Exchange";
    } catch (e) {
        statusText.text = "✗ Not connected - Run Python bridge first";
    }
    
    // Tabs
    var tabs = win.add("tabbedpanel");
    tabs.alignChildren = "fill";
    tabs.preferredSize = [350, 450];
    
    // === Generate Tab ===
    var genTab = tabs.add("tab", undefined, "Generate");
    genTab.orientation = "column";
    genTab.alignChildren = "fill";
    genTab.margins = 10;
    
    genTab.add("statictext", undefined, "Prompt:");
    var promptInput = genTab.add("edittext", undefined, "", {multiline: true});
    promptInput.size = [300, 80];
    promptInput.helpTip = "Describe the image you want to generate";
    
    genTab.add("statictext", undefined, "Duration (seconds):");
    var durationInput = genTab.add("edittext", undefined, "5");
    durationInput.size = [80, 20];
    
    var genBtn = genTab.add("button", undefined, "Generate Image");
    genBtn.onClick = function() {
        var prompt = promptInput.text;
        if (!prompt) {
            alert("Please enter a prompt!");
            return;
        }
        var duration = parseFloat(durationInput.text) || 5;
        generateImage(prompt, { duration: duration });
    };
    
    // === Animate Tab ===
    var animTab = tabs.add("tab", undefined, "Animate");
    animTab.orientation = "column";
    animTab.alignChildren = "fill";
    animTab.margins = 10;
    
    animTab.add("statictext", undefined, "Image Path:");
    var imagePathInput = animTab.add("edittext", undefined, "");
    imagePathInput.size = [250, 20];
    
    var browseBtn = animTab.add("button", undefined, "Browse...");
    browseBtn.onClick = function() {
        var file = File.openDialog("Select image to animate", "Images:*.png;*.jpg;*.jpeg");
        if (file) {
            imagePathInput.text = file.fsName;
        }
    };
    
    animTab.add("statictext", undefined, "Motion Description:");
    var motionInput = animTab.add("edittext", undefined, "", {multiline: true});
    motionInput.size = [300, 60];
    motionInput.helpTip = "Describe the motion (e.g., 'character waves hello')";
    
    var animateBtn = animTab.add("button", undefined, "Animate Image");
    animateBtn.onClick = function() {
        var imagePath = imagePathInput.text;
        var motion = motionInput.text;
        
        if (!imagePath || !motion) {
            alert("Please provide both image path and motion description!");
            return;
        }
        
        animateImage(imagePath, motion);
    };
    
    // === Batch Tab ===
    var batchTab = tabs.add("tab", undefined, "Batch");
    batchTab.orientation = "column";
    batchTab.alignChildren = "fill";
    batchTab.margins = 10;
    
    batchTab.add("statictext", undefined, "Prompts (one per line):");
    var batchInput = batchTab.add("edittext", undefined, "", {multiline: true});
    batchInput.size = [300, 120];
    
    batchTab.add("statictext", undefined, "Duration per image (seconds):");
    var batchDuration = batchTab.add("edittext", undefined, "2");
    batchDuration.size = [80, 20];
    
    var batchBtn = batchTab.add("button", undefined, "Generate Sequence");
    batchBtn.onClick = function() {
        var text = batchInput.text;
        if (!text) {
            alert("Please enter prompts!");
            return;
        }
        
        var prompts = text.split("\n").filter(function(p) { return p.trim(); });
        var duration = parseFloat(batchDuration.text) || 2;
        
        batchGenerate(prompts, { duration: duration });
    };
    
    // === Settings Tab ===
    var settingsTab = tabs.add("tab", undefined, "Settings");
    settingsTab.orientation = "column";
    settingsTab.alignChildren = "fill";
    settingsTab.margins = 10;
    
    settingsTab.add("statictext", undefined, "API URL:");
    var apiInput = settingsTab.add("edittext", undefined, CONFIG.API_URL);
    apiInput.size = [300, 20];
    
    settingsTab.add("statictext", undefined, "File Server URL:");
    var fileInput = settingsTab.add("edittext", undefined, CONFIG.FILE_SERVER_URL);
    fileInput.size = [300, 20];
    
    var saveBtn = settingsTab.add("button", undefined, "Save Settings");
    saveBtn.onClick = function() {
        CONFIG.API_URL = apiInput.text;
        CONFIG.FILE_SERVER_URL = fileInput.text;
        alert("Settings saved!");
    };
    
    // Footer
    win.add("statictext", undefined, "Graydient Exchange v1.0");
    
    return win;
}

// Main
function main() {
    var panel = buildPanel();
    if (panel instanceof Window) {
        panel.show();
    }
}

main();
