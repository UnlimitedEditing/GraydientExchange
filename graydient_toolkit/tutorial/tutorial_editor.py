"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    tutorial/tutorial_editor.py                               ║
║                      Tutorial Editor Tool                                   ║
║                                                                             ║
║  GUI tool for creating and editing interactive tutorials.                   ║
║  Supports visual region selection, media upload, and preview.               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, List, Optional

from .engine import (
    TutorialDefinition,
    TutorialStep,
    TutorialSession,
    HighlightRegion,
    MediaContent,
    StepTrigger,
)


class TutorialEditor:
    """
    GUI editor for creating and editing tutorials.
    
    Features:
    - Visual step management (add, remove, reorder)
    - Region selector for highlight areas
    - Media upload (images, videos)
    - Slideshow creation
    - Live preview
    - Import/Export JSON
    
    Example:
        >>> from graydient_toolkit.tutorial import TutorialEditor
        >>> 
        >>> editor = TutorialEditor()
        >>> editor.run()
    """
    
    def __init__(self, tutorials_dir: Optional[Path] = None):
        """
        Initialize the tutorial editor.
        
        Args:
            tutorials_dir: Directory to save tutorials (default: ~/.graydient_toolkit/tutorials)
        """
        self._tutorials_dir = tutorials_dir or Path.home() / ".graydient_toolkit" / "tutorials"
        self._tutorials_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_tutorial: Optional[TutorialDefinition] = None
        self._current_step_index: int = -1
        
        # UI elements
        self._root: Optional[tk.Tk] = None
        self._step_listbox: Optional[tk.Listbox] = None
        self._step_editor_frame: Optional[ttk.Frame] = None
        
        # Step editor fields
        self._step_fields: Dict[str, Any] = {}
    
    def run(self) -> None:
        """Run the tutorial editor GUI."""
        self._root = tk.Tk()
        self._root.title("Graydient Tutorial Editor")
        self._root.geometry("1200x800")
        self._root.minsize(1000, 700)
        
        self._setup_menu()
        self._setup_ui()
        
        # Create a new tutorial by default
        self._new_tutorial()
        
        self._root.mainloop()
    
    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = tk.Menu(self._root)
        self._root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Tutorial", command=self._new_tutorial, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self._open_tutorial, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._save_tutorial, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._save_tutorial_as)
        file_menu.add_separator()
        file_menu.add_command(label="Import JSON...", command=self._import_json)
        file_menu.add_command(label="Export JSON...", command=self._export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Add Step", command=self._add_step, accelerator="Ctrl+Shift+N")
        edit_menu.add_command(label="Delete Step", command=self._delete_step)
        edit_menu.add_command(label="Duplicate Step", command=self._duplicate_step)
        edit_menu.add_separator()
        edit_menu.add_command(label="Move Up", command=self._move_step_up)
        edit_menu.add_command(label="Move Down", command=self._move_step_down)
        
        # Preview menu
        preview_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Preview", menu=preview_menu)
        preview_menu.add_command(label="Preview Tutorial", command=self._preview_tutorial)
        preview_menu.add_command(label="Preview Current Step", command=self._preview_step)
        
        # Bind keyboard shortcuts
        self._root.bind("<Control-n>", lambda e: self._new_tutorial())
        self._root.bind("<Control-o>", lambda e: self._open_tutorial())
        self._root.bind("<Control-s>", lambda e: self._save_tutorial())
        self._root.bind("<Control-Shift-N>", lambda e: self._add_step())
    
    def _setup_ui(self) -> None:
        """Set up the main UI."""
        # Main container with padding
        main_frame = ttk.Frame(self._root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # === Header ===
        header = ttk.Frame(main_frame)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        ttk.Label(header, text="Tutorial Editor", font=("Helvetica", 18, "bold")).pack(side=tk.LEFT)
        
        # === Left Panel: Step List ===
        left_panel = ttk.LabelFrame(main_frame, text="Steps", padding="10")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)
        
        # Step listbox with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self._step_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            font=("Consolas", 11),
            height=20,
        )
        self._step_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=self._step_listbox.yview)
        
        self._step_listbox.bind("<<ListboxSelect>>", self._on_step_select)
        
        # Step list buttons
        btn_frame = ttk.Frame(left_panel)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        
        ttk.Button(btn_frame, text="Add", command=self._add_step).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Delete", command=self._delete_step).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="↑", command=self._move_step_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="↓", command=self._move_step_down).pack(side=tk.LEFT)
        
        # === Right Panel: Step Editor ===
        right_panel = ttk.LabelFrame(main_frame, text="Step Editor", padding="10")
        right_panel.grid(row=1, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        
        # Create scrollable step editor
        canvas = tk.Canvas(right_panel)
        scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=canvas.yview)
        self._step_editor_frame = ttk.Frame(canvas)
        
        self._step_editor_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self._step_editor_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self._setup_step_editor_fields()
        
        # === Bottom Panel: Tutorial Info ===
        bottom_panel = ttk.LabelFrame(main_frame, text="Tutorial Info", padding="10")
        bottom_panel.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        self._setup_tutorial_info_fields(bottom_panel)
    
    def _setup_step_editor_fields(self) -> None:
        """Set up the step editor form fields."""
        frame = self._step_editor_frame
        
        # Step ID
        row = 0
        ttk.Label(frame, text="Step ID:").grid(row=row, column=0, sticky="w", pady=5)
        self._step_fields["id"] = ttk.Entry(frame, width=40)
        self._step_fields["id"].grid(row=row, column=1, sticky="ew", pady=5)
        
        # Step Title
        row += 1
        ttk.Label(frame, text="Title:").grid(row=row, column=0, sticky="w", pady=5)
        self._step_fields["title"] = ttk.Entry(frame, width=40)
        self._step_fields["title"].grid(row=row, column=1, sticky="ew", pady=5)
        
        # Step Text
        row += 1
        ttk.Label(frame, text="Text:").grid(row=row, column=0, sticky="nw", pady=5)
        self._step_fields["text"] = tk.Text(frame, width=40, height=6, wrap=tk.WORD)
        self._step_fields["text"].grid(row=row, column=1, sticky="ew", pady=5)
        
        # Highlight Region
        row += 1
        highlight_frame = ttk.LabelFrame(frame, text="Highlight Region", padding="10")
        highlight_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        
        # Highlight coordinates
        coord_frame = ttk.Frame(highlight_frame)
        coord_frame.pack(fill=tk.X)
        
        self._step_fields["highlight_x"] = self._create_labeled_entry(coord_frame, "X:", 0, 0, width=8)
        self._step_fields["highlight_y"] = self._create_labeled_entry(coord_frame, "Y:", 0, 2, width=8)
        self._step_fields["highlight_width"] = self._create_labeled_entry(coord_frame, "W:", 0, 4, width=8)
        self._step_fields["highlight_height"] = self._create_labeled_entry(coord_frame, "H:", 0, 6, width=8)
        
        # Highlight options
        opts_frame = ttk.Frame(highlight_frame)
        opts_frame.pack(fill=tk.X, pady=(10, 0))
        
        self._step_fields["highlight_use_percent"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_frame, text="Use percentages", variable=self._step_fields["highlight_use_percent"]).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(opts_frame, text="Shape:").pack(side=tk.LEFT, padx=(0, 5))
        self._step_fields["highlight_shape"] = ttk.Combobox(opts_frame, values=["rectangle", "circle", "rounded"], width=10, state="readonly")
        self._step_fields["highlight_shape"].set("rectangle")
        self._step_fields["highlight_shape"].pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(opts_frame, text="Select on Screen...", command=self._select_region_on_screen).pack(side=tk.LEFT)
        
        # Media
        row += 1
        media_frame = ttk.LabelFrame(frame, text="Media", padding="10")
        media_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        
        media_type_frame = ttk.Frame(media_frame)
        media_type_frame.pack(fill=tk.X)
        
        ttk.Label(media_type_frame, text="Type:").pack(side=tk.LEFT, padx=(0, 5))
        self._step_fields["media_type"] = ttk.Combobox(media_type_frame, values=["none", "image", "video", "slideshow"], width=12, state="readonly")
        self._step_fields["media_type"].set("none")
        self._step_fields["media_type"].pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(media_type_frame, text="Browse...", command=self._browse_media).pack(side=tk.LEFT)
        
        self._step_fields["media_path"] = ttk.Entry(media_frame, width=50)
        self._step_fields["media_path"].pack(fill=tk.X, pady=(10, 0))
        
        # Trigger
        row += 1
        trigger_frame = ttk.Frame(frame)
        trigger_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(trigger_frame, text="Advance Trigger:").pack(side=tk.LEFT, padx=(0, 5))
        self._step_fields["trigger"] = ttk.Combobox(trigger_frame, values=["MANUAL", "CLICK", "INPUT", "DELAY", "EVENT"], width=12, state="readonly")
        self._step_fields["trigger"].set("MANUAL")
        self._step_fields["trigger"].pack(side=tk.LEFT, padx=(0, 10))
        
        self._step_fields["skippable"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(trigger_frame, text="Skippable", variable=self._step_fields["skippable"]).pack(side=tk.LEFT)
        
        # Save button
        row += 1
        ttk.Button(frame, text="Save Step Changes", command=self._save_current_step).grid(row=row, column=0, columnspan=2, pady=20)
        
        # Disable editor initially
        self._set_editor_enabled(False)
    
    def _create_labeled_entry(self, parent, label, row, col, width=10) -> ttk.Entry:
        """Create a labeled entry field."""
        ttk.Label(parent, text=label).grid(row=row, column=col, padx=(10 if col > 0 else 0, 5))
        entry = ttk.Entry(parent, width=width)
        entry.grid(row=row, column=col + 1)
        return entry
    
    def _setup_tutorial_info_fields(self, parent: ttk.Frame) -> None:
        """Set up tutorial info fields."""
        # Tutorial ID
        ttk.Label(parent, text="ID:").grid(row=0, column=0, sticky="w", padx=5)
        self._tutorial_id_entry = ttk.Entry(parent, width=30)
        self._tutorial_id_entry.grid(row=0, column=1, sticky="w", padx=5)
        
        # Tutorial Title
        ttk.Label(parent, text="Title:").grid(row=0, column=2, sticky="w", padx=5)
        self._tutorial_title_entry = ttk.Entry(parent, width=30)
        self._tutorial_title_entry.grid(row=0, column=3, sticky="w", padx=5)
        
        # Description
        ttk.Label(parent, text="Description:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self._tutorial_desc_entry = ttk.Entry(parent, width=80)
        self._tutorial_desc_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        # Difficulty & Category
        ttk.Label(parent, text="Difficulty:").grid(row=2, column=0, sticky="w", padx=5)
        self._tutorial_difficulty = ttk.Combobox(parent, values=["beginner", "intermediate", "advanced"], width=15, state="readonly")
        self._tutorial_difficulty.set("beginner")
        self._tutorial_difficulty.grid(row=2, column=1, sticky="w", padx=5)
        
        ttk.Label(parent, text="Category:").grid(row=2, column=2, sticky="w", padx=5)
        self._tutorial_category = ttk.Entry(parent, width=20)
        self._tutorial_category.grid(row=2, column=3, sticky="w", padx=5)
    
    def _set_editor_enabled(self, enabled: bool) -> None:
        """Enable or disable the step editor."""
        state = "normal" if enabled else "disabled"
        
        for field in self._step_fields.values():
            if isinstance(field, (ttk.Entry, tk.Text, ttk.Combobox)):
                field.config(state=state)
            elif isinstance(field, tk.BooleanVar):
                # Can't disable variables, skip
                pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────────────────
    
    def _on_step_select(self, event: Any) -> None:
        """Handle step selection in listbox."""
        selection = self._step_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        self._current_step_index = index
        
        # Load step data into editor
        if self._current_tutorial and 0 <= index < len(self._current_tutorial.steps):
            step = self._current_tutorial.steps[index]
            self._load_step_into_editor(step)
            self._set_editor_enabled(True)
    
    def _load_step_into_editor(self, step: TutorialStep) -> None:
        """Load step data into editor fields."""
        self._step_fields["id"].delete(0, tk.END)
        self._step_fields["id"].insert(0, step.id)
        
        self._step_fields["title"].delete(0, tk.END)
        self._step_fields["title"].insert(0, step.title)
        
        self._step_fields["text"].delete("1.0", tk.END)
        self._step_fields["text"].insert("1.0", step.text)
        
        # Highlight
        if step.highlight:
            self._step_fields["highlight_x"].delete(0, tk.END)
            self._step_fields["highlight_x"].insert(0, str(step.highlight.x))
            
            self._step_fields["highlight_y"].delete(0, tk.END)
            self._step_fields["highlight_y"].insert(0, str(step.highlight.y))
            
            self._step_fields["highlight_width"].delete(0, tk.END)
            self._step_fields["highlight_width"].insert(0, str(step.highlight.width))
            
            self._step_fields["highlight_height"].delete(0, tk.END)
            self._step_fields["highlight_height"].insert(0, str(step.highlight.height))
            
            self._step_fields["highlight_use_percent"].set(step.highlight.use_percent)
            self._step_fields["highlight_shape"].set(step.highlight.shape)
        
        # Media
        if step.media:
            self._step_fields["media_type"].set(step.media.media_type)
            if isinstance(step.media.src, str):
                self._step_fields["media_path"].delete(0, tk.END)
                self._step_fields["media_path"].insert(0, step.media.src)
        
        # Trigger
        self._step_fields["trigger"].set(step.trigger.name)
        self._step_fields["skippable"].set(step.skippable)
    
    def _save_current_step(self) -> None:
        """Save the current step from editor fields."""
        if not self._current_tutorial or self._current_step_index < 0:
            return
        
        # Build highlight region
        try:
            highlight = HighlightRegion(
                x=float(self._step_fields["highlight_x"].get() or 0),
                y=float(self._step_fields["highlight_y"].get() or 0),
                width=float(self._step_fields["highlight_width"].get() or 100),
                height=float(self._step_fields["highlight_height"].get() or 50),
                use_percent=self._step_fields["highlight_use_percent"].get(),
                shape=self._step_fields["highlight_shape"].get(),
            )
        except ValueError:
            highlight = None
        
        # Build media content
        media_type = self._step_fields["media_type"].get()
        media = None
        if media_type != "none":
            media_path = self._step_fields["media_path"].get()
            if media_path:
                media = MediaContent(
                    media_type=media_type,
                    src=media_path,
                )
        
        # Build step
        step = TutorialStep(
            id=self._step_fields["id"].get() or f"step-{self._current_step_index + 1}",
            title=self._step_fields["title"].get() or "Untitled Step",
            text=self._step_fields["text"].get("1.0", tk.END).strip(),
            highlight=highlight,
            media=media,
            trigger=StepTrigger[self._step_fields["trigger"].get()],
            skippable=self._step_fields["skippable"].get(),
        )
        
        # Update tutorial
        self._current_tutorial.steps[self._current_step_index] = step
        
        # Update listbox
        self._step_listbox.delete(self._current_step_index)
        self._step_listbox.insert(self._current_step_index, f"{step.id}: {step.title}")
        
        messagebox.showinfo("Success", "Step saved!")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tutorial Operations
    # ─────────────────────────────────────────────────────────────────────────
    
    def _new_tutorial(self) -> None:
        """Create a new tutorial."""
        self._current_tutorial = TutorialDefinition(
            id="new-tutorial",
            title="New Tutorial",
            description="",
        )
        self._current_step_index = -1
        
        # Clear UI
        self._step_listbox.delete(0, tk.END)
        self._tutorial_id_entry.delete(0, tk.END)
        self._tutorial_id_entry.insert(0, self._current_tutorial.id)
        self._tutorial_title_entry.delete(0, tk.END)
        self._tutorial_title_entry.insert(0, self._current_tutorial.title)
        self._tutorial_desc_entry.delete(0, tk.END)
        
        self._set_editor_enabled(False)
    
    def _open_tutorial(self) -> None:
        """Open an existing tutorial."""
        file_path = filedialog.askopenfilename(
            initialdir=self._tutorials_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        
        if not file_path:
            return
        
        try:
            self._current_tutorial = TutorialDefinition.load(file_path)
            
            # Update UI
            self._step_listbox.delete(0, tk.END)
            for step in self._current_tutorial.steps:
                self._step_listbox.insert(tk.END, f"{step.id}: {step.title}")
            
            self._tutorial_id_entry.delete(0, tk.END)
            self._tutorial_id_entry.insert(0, self._current_tutorial.id)
            self._tutorial_title_entry.delete(0, tk.END)
            self._tutorial_title_entry.insert(0, self._current_tutorial.title)
            self._tutorial_desc_entry.delete(0, tk.END)
            self._tutorial_desc_entry.insert(0, self._current_tutorial.description)
            
            self._set_editor_enabled(False)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tutorial: {e}")
    
    def _save_tutorial(self) -> None:
        """Save the current tutorial."""
        if not self._current_tutorial:
            return
        
        # Update tutorial info from fields
        self._current_tutorial.id = self._tutorial_id_entry.get()
        self._current_tutorial.title = self._tutorial_title_entry.get()
        self._current_tutorial.description = self._tutorial_desc_entry.get()
        self._current_tutorial.difficulty = self._tutorial_difficulty.get()
        self._current_tutorial.category = self._tutorial_category.get()
        
        file_path = self._tutorials_dir / f"{self._current_tutorial.id}.json"
        
        try:
            self._current_tutorial.save(file_path)
            messagebox.showinfo("Success", f"Tutorial saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save tutorial: {e}")
    
    def _save_tutorial_as(self) -> None:
        """Save tutorial with a new name."""
        if not self._current_tutorial:
            return
        
        file_path = filedialog.asksaveasfilename(
            initialdir=self._tutorials_dir,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        
        if file_path:
            try:
                self._current_tutorial.save(file_path)
                messagebox.showinfo("Success", f"Tutorial saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save tutorial: {e}")
    
    def _import_json(self) -> None:
        """Import tutorial from JSON."""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        
        if file_path:
            self._open_tutorial()  # Same as open
    
    def _export_json(self) -> None:
        """Export tutorial to JSON."""
        self._save_tutorial_as()  # Same as save as
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step Operations
    # ─────────────────────────────────────────────────────────────────────────
    
    def _add_step(self) -> None:
        """Add a new step."""
        if not self._current_tutorial:
            return
        
        step_num = len(self._current_tutorial.steps) + 1
        new_step = TutorialStep(
            id=f"step-{step_num}",
            title=f"Step {step_num}",
            text="",
        )
        
        self._current_tutorial.steps.append(new_step)
        self._step_listbox.insert(tk.END, f"{new_step.id}: {new_step.title}")
        
        # Select the new step
        self._step_listbox.selection_clear(0, tk.END)
        self._step_listbox.selection_set(tk.END)
        self._step_listbox.see(tk.END)
        self._on_step_select(None)
    
    def _delete_step(self) -> None:
        """Delete the selected step."""
        if not self._current_tutorial or self._current_step_index < 0:
            return
        
        if not messagebox.askyesno("Confirm", "Delete this step?"):
            return
        
        del self._current_tutorial.steps[self._current_step_index]
        self._step_listbox.delete(self._current_step_index)
        
        self._current_step_index = -1
        self._set_editor_enabled(False)
    
    def _duplicate_step(self) -> None:
        """Duplicate the selected step."""
        if not self._current_tutorial or self._current_step_index < 0:
            return
        
        original = self._current_tutorial.steps[self._current_step_index]
        
        # Create a copy with new ID
        import copy
        new_step = copy.deepcopy(original)
        new_step.id = f"{original.id}-copy"
        
        insert_index = self._current_step_index + 1
        self._current_tutorial.steps.insert(insert_index, new_step)
        self._step_listbox.insert(insert_index, f"{new_step.id}: {new_step.title}")
    
    def _move_step_up(self) -> None:
        """Move the selected step up."""
        if not self._current_tutorial or self._current_step_index <= 0:
            return
        
        # Swap steps
        idx = self._current_step_index
        self._current_tutorial.steps[idx], self._current_tutorial.steps[idx - 1] = \
            self._current_tutorial.steps[idx - 1], self._current_tutorial.steps[idx]
        
        # Update listbox
        self._step_listbox.delete(idx - 1, idx)
        for i in [idx - 1, idx]:
            step = self._current_tutorial.steps[i]
            self._step_listbox.insert(i, f"{step.id}: {step.title}")
        
        self._current_step_index -= 1
        self._step_listbox.selection_set(self._current_step_index)
    
    def _move_step_down(self) -> None:
        """Move the selected step down."""
        if not self._current_tutorial:
            return
        
        idx = self._current_step_index
        if idx < 0 or idx >= len(self._current_tutorial.steps) - 1:
            return
        
        # Swap steps
        self._current_tutorial.steps[idx], self._current_tutorial.steps[idx + 1] = \
            self._current_tutorial.steps[idx + 1], self._current_tutorial.steps[idx]
        
        # Update listbox
        self._step_listbox.delete(idx, idx + 2)
        for i in [idx, idx + 1]:
            step = self._current_tutorial.steps[i]
            self._step_listbox.insert(i, f"{step.id}: {step.title}")
        
        self._current_step_index += 1
        self._step_listbox.selection_set(self._current_step_index)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Media & Region Selection
    # ─────────────────────────────────────────────────────────────────────────
    
    def _browse_media(self) -> None:
        """Browse for media file."""
        media_type = self._step_fields["media_type"].get()
        
        if media_type == "image":
            filetypes = [("Image files", "*.png *.jpg *.jpeg *.gif *.webp"), ("All files", "*.*")]
        elif media_type == "video":
            filetypes = [("Video files", "*.mp4 *.webm *.mov"), ("All files", "*.*")]
        else:
            filetypes = [("All files", "*.*")]
        
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        
        if file_path:
            self._step_fields["media_path"].delete(0, tk.END)
            self._step_fields["media_path"].insert(0, file_path)
    
    def _select_region_on_screen(self) -> None:
        """Open a screen region selector."""
        messagebox.showinfo("Info", "Screen region selector would open here.\n\nFor now, enter coordinates manually.")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Preview
    # ─────────────────────────────────────────────────────────────────────────
    
    def _preview_tutorial(self) -> None:
        """Preview the entire tutorial."""
        if not self._current_tutorial:
            return
        
        messagebox.showinfo("Preview", f"Previewing tutorial: {self._current_tutorial.title}\n\n({self._current_tutorial.step_count} steps)")
    
    def _preview_step(self) -> None:
        """Preview the current step."""
        if not self._current_tutorial or self._current_step_index < 0:
            return
        
        step = self._current_tutorial.steps[self._current_step_index]
        messagebox.showinfo("Preview", f"Step: {step.title}\n\n{step.text[:200]}...")


def main():
    """Main entry point for the tutorial editor."""
    editor = TutorialEditor()
    editor.run()


if __name__ == "__main__":
    main()
