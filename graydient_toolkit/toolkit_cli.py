"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        toolkit_cli.py                                        ║
║              Command-Line Interface for Graydient Toolkit                   ║
║                                                                             ║
║  Provides CLI commands for:                                                 ║
║    • Managing method registry                                               ║
║    • Parsing and testing commands                                           ║
║    • Configuration management                                               ║
║    • Preview dataset management                                             ║
║    • Tutorial creation and editing                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def cmd_registry(args: argparse.Namespace) -> int:
    """Handle registry commands."""
    print_header("Method Registry")
    
    try:
        from graydient_exchange import Exchange
        from graydient_toolkit import MethodRegistry
        
        # Initialize exchange
        exchange = Exchange()
        registry = MethodRegistry(exchange)
        
        if args.refresh:
            print("Refreshing registry from API...")
            result = registry.refresh(force=True)
            print(f"  Loaded {result['workflows']} workflows, {result['concepts']} concepts")
        
        if args.list:
            print("\nAvailable Workflows:")
            for wf in sorted(registry.all_workflows, key=lambda x: x.slug):
                caps = ", ".join(c.value for c in wf.capabilities[:3])
                print(f"  {wf.slug:20} - {wf.short_description[:50] or 'No description'}")
                print(f"                       Capabilities: {caps}")
            
            print("\nAvailable Commands:")
            for cmd, target in sorted(registry.get_command_mapping().items()):
                print(f"  {cmd:12} → {target}")
        
        if args.search:
            print(f"\nSearching for '{args.search}':")
            results = registry.search(args.search)
            for method in results:
                print(f"  {method.slug:20} ({method.category.value})")
        
        if args.info:
            method = registry.get_method(args.info)
            if method:
                print(f"\n{method.format_help()}")
            else:
                print(f"Method not found: {args.info}")
        
        if args.stats:
            registry.print_summary()
        
        return 0
    
    except ImportError as e:
        print(f"Error: Required module not found: {e}")
        print("Make sure graydient_exchange is installed.")
        return 1
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_parse(args: argparse.Namespace) -> int:
    """Handle parse commands."""
    print_header("Command Parser")
    
    try:
        from graydient_toolkit import CommandParserEngine, quick_parse
        
        if args.command:
            print(f"Input: {args.command}\n")
            
            if args.registry:
                from graydient_exchange import Exchange
                from graydient_toolkit import MethodRegistry
                
                exchange = Exchange()
                registry = MethodRegistry(exchange)
                parser = CommandParserEngine(registry)
            else:
                parser = CommandParserEngine(registry=None)
            
            result = parser.parse(args.command)
            
            print(result.format_for_display())
            
            if args.to_json:
                print("\nJSON Output:")
                print(json.dumps({
                    "workflow": result.workflow,
                    "prompt": result.prompt,
                    "negative": result.negative_prompt,
                    "parameters": result.parameters,
                    "is_valid": result.is_valid,
                    "errors": result.errors,
                    "warnings": result.warnings,
                }, indent=2))
        
        else:
            # Interactive mode
            print("Enter commands to parse (Ctrl+C to exit):")
            print("Examples:")
            print("  /draw a cat --seed 42")
            print("  /animate walking [blurry, low quality]")
            print()
            
            while True:
                try:
                    command = input("> ").strip()
                    if command:
                        result = quick_parse(command)
                        print(f"  Workflow: {result.workflow}")
                        print(f"  Prompt: {result.prompt[:60]}...")
                        print(f"  Parameters: {result.parameters}")
                        print()
                
                except KeyboardInterrupt:
                    print("\nExiting...")
                    break
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_config(args: argparse.Namespace) -> int:
    """Handle config commands."""
    print_header("Configuration")
    
    try:
        from graydient_toolkit import ConfigManager
        
        config = ConfigManager()
        
        if args.show:
            config.print_summary()
        
        if args.get:
            value = config.get(args.get)
            print(f"{args.get} = {value}")
        
        if args.set:
            key, value = args.set
            # Try to parse as JSON
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
            
            config.set(key, parsed_value)
            config.save()
            print(f"Set {key} = {parsed_value}")
        
        if args.alias:
            alias, target = args.alias
            config.add_alias(alias, target)
            config.save()
            print(f"Added alias: {alias} → {target}")
        
        if args.reset:
            if input("Are you sure? (yes/no): ").lower() == "yes":
                config.reset()
                print("Configuration reset to defaults.")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_previews(args: argparse.Namespace) -> int:
    """Handle preview commands."""
    print_header("Preview Dataset")
    
    try:
        from graydient_toolkit import PreviewDataset
        
        previews = PreviewDataset()
        
        if args.stats:
            previews.print_summary()
        
        if args.download:
            method_slug, category, url = args.download
            print(f"Downloading preview for {method_slug}...")
            result = previews.download(method_slug, category, url)
            if result:
                print(f"  Saved to: {result.path}")
            else:
                print("  Download failed")
        
        if args.list:
            category = args.list
            print(f"\nMethods with {category} previews:")
            
            # Scan directory
            base_dir = previews._base_dir / f"{category}s"
            if base_dir.exists():
                for method_dir in sorted(base_dir.iterdir()):
                    if method_dir.is_dir():
                        preview_files = list(method_dir.glob("*"))
                        preview_files = [f for f in preview_files if f.name != "info.json"]
                        if preview_files:
                            print(f"  {method_dir.name}: {len(preview_files)} preview(s)")
        
        if args.cleanup:
            removed = previews.cleanup_orphans()
            print(f"Removed {removed} orphaned files")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_tutorial(args: argparse.Namespace) -> int:
    """Handle tutorial commands."""
    print_header("Tutorial System")
    
    try:
        from graydient_toolkit.tutorial import TutorialEngine, TutorialEditor
        
        if args.edit:
            print("Launching Tutorial Editor...")
            editor = TutorialEditor()
            editor.run()
            return 0
        
        if args.list:
            engine = TutorialEngine()
            tutorials = engine.list_tutorials()
            
            print("\nAvailable Tutorials:")
            for t in tutorials:
                print(f"\n  {t['id']}")
                print(f"    Title: {t['title']}")
                print(f"    Difficulty: {t['difficulty']}")
                print(f"    Steps: {t['step_count']}")
                print(f"    Duration: ~{t['estimated_duration']} min")
        
        if args.run:
            tutorial_id = args.run
            print(f"Running tutorial: {tutorial_id}")
            
            engine = TutorialEngine()
            if engine.load_tutorial(tutorial_id):
                engine.start()
                print(f"Tutorial started! {engine.total_steps} steps.")
                print("Use engine.next_step() to advance.")
            else:
                print(f"Failed to load tutorial: {tutorial_id}")
                return 1
        
        return 0
    
    except ImportError:
        print("Error: Tutorial system not available.")
        return 1
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="graydient-toolkit",
        description="Graydient Toolkit CLI - Manage methods, parse commands, and create tutorials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh and list all methods
  graydient-toolkit registry --refresh --list

  # Parse a command
  graydient-toolkit parse "/draw a cat --seed 42"

  # Show configuration
  graydient-toolkit config --show

  # Launch tutorial editor
  graydient-toolkit tutorial --edit
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Registry command
    registry_parser = subparsers.add_parser("registry", help="Manage method registry")
    registry_parser.add_argument("--refresh", action="store_true", help="Refresh from API")
    registry_parser.add_argument("--list", action="store_true", help="List all methods")
    registry_parser.add_argument("--search", metavar="QUERY", help="Search methods")
    registry_parser.add_argument("--info", metavar="METHOD", help="Show method details")
    registry_parser.add_argument("--stats", action="store_true", help="Show registry stats")
    registry_parser.set_defaults(func=cmd_registry)
    
    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parse commands")
    parse_parser.add_argument("command", nargs="?", help="Command to parse")
    parse_parser.add_argument("--registry", action="store_true", help="Use registry for validation")
    parse_parser.add_argument("--to-json", action="store_true", help="Output as JSON")
    parse_parser.set_defaults(func=cmd_parse)
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--show", action="store_true", help="Show all config")
    config_parser.add_argument("--get", metavar="KEY", help="Get a config value")
    config_parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set a config value")
    config_parser.add_argument("--alias", nargs=2, metavar=("ALIAS", "TARGET"), help="Add method alias")
    config_parser.add_argument("--reset", action="store_true", help="Reset to defaults")
    config_parser.set_defaults(func=cmd_config)
    
    # Previews command
    previews_parser = subparsers.add_parser("previews", help="Manage preview dataset")
    previews_parser.add_argument("--stats", action="store_true", help="Show preview stats")
    previews_parser.add_argument("--download", nargs=3, metavar=("SLUG", "CATEGORY", "URL"), help="Download preview")
    previews_parser.add_argument("--list", metavar="CATEGORY", help="List previews (workflow/concept)")
    previews_parser.add_argument("--cleanup", action="store_true", help="Remove orphaned files")
    previews_parser.set_defaults(func=cmd_previews)
    
    # Tutorial command
    tutorial_parser = subparsers.add_parser("tutorial", help="Manage tutorials")
    tutorial_parser.add_argument("--list", action="store_true", help="List tutorials")
    tutorial_parser.add_argument("--run", metavar="ID", help="Run a tutorial")
    tutorial_parser.add_argument("--edit", action="store_true", help="Launch tutorial editor")
    tutorial_parser.set_defaults(func=cmd_tutorial)
    
    # Parse arguments
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Execute command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
