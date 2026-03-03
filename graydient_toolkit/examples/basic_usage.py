"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    Basic Usage Example                                       ║
║                                                                             ║
║  Demonstrates the core functionality of the Graydient Toolkit.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys

# Add toolkit to path
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from graydient_exchange import Exchange
from graydient_toolkit import (
    MethodRegistry,
    CommandParserEngine,
    InputModifier,
    ConfigManager,
)


def main():
    """Run the basic usage example."""
    print("=" * 60)
    print("Graydient Toolkit - Basic Usage Example")
    print("=" * 60)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Initialize the Exchange
    # ─────────────────────────────────────────────────────────────────────────
    print("\n1. Initializing Graydient Exchange...")
    
    # The Exchange will automatically use GRAYDIENT_KEY from environment
    exchange = Exchange()
    print("   ✓ Exchange initialized")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Create the Method Registry
    # ─────────────────────────────────────────────────────────────────────────
    print("\n2. Creating Method Registry...")
    
    registry = MethodRegistry(exchange, auto_refresh=True)
    
    # Refresh from API (this will cache results)
    result = registry.refresh()
    print(f"   ✓ Loaded {result['workflows']} workflows, {result['concepts']} concepts")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: List Available Commands
    # ─────────────────────────────────────────────────────────────────────────
    print("\n3. Available Commands:")
    
    commands = registry.get_command_mapping()
    for cmd, workflow in sorted(commands.items())[:10]:  # Show first 10
        print(f"   {cmd:12} → {workflow}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Parse Telegram-Style Commands
    # ─────────────────────────────────────────────────────────────────────────
    print("\n4. Parsing Commands...")
    
    parser = CommandParserEngine(registry)
    
    # Example commands
    test_commands = [
        "/draw a beautiful sunset over mountains --seed 42",
        "/animate a walking robot [blurry, distorted] --fps 24",
        "/style oil painting --strength 0.8",
    ]
    
    for cmd_text in test_commands:
        print(f"\n   Input: {cmd_text}")
        
        parsed = parser.parse(cmd_text)
        
        print(f"   Workflow: {parsed.workflow}")
        print(f"   Prompt: {parsed.prompt[:50]}...")
        print(f"   Negative: {parsed.negative_prompt or '(none)'}")
        print(f"   Parameters: {parsed.parameters}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Transform for Exchange
    # ─────────────────────────────────────────────────────────────────────────
    print("\n5. Transforming for Exchange...")
    
    modifier = InputModifier(registry)
    
    parsed = parser.parse("/draw a cyberpunk cityscape --seed 123 --guidance 8.0")
    result = modifier.transform(parsed)
    
    print(f"   Workflow: {result.workflow}")
    print(f"   Parameters:")
    for key, value in result.params.items():
        print(f"     {key}: {value}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Execute (commented out to avoid actual API calls in example)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n6. Execution (simulated)...")
    
    print("   Would execute:")
    print(f"     exchange.run('{result.workflow}', {result.params})")
    print("   ✓ (Skipped in example to avoid API calls)")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Configuration
    # ─────────────────────────────────────────────────────────────────────────
    print("\n7. Configuration...")
    
    config = ConfigManager()
    
    # Add a custom alias
    config.add_alias("p", "portrait")
    config.save()
    
    print("   ✓ Added alias: p → portrait")
    print(f"   Current aliases: {list(config.get_aliases().keys())[:5]}...")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Example Complete!")
    print("=" * 60)
    print("\nKey Features Demonstrated:")
    print("  ✓ Dynamic method discovery from API")
    print("  ✓ Telegram-style command parsing")
    print("  ✓ Negative prompt extraction [like this]")
    print("  ✓ Parameter validation and defaults")
    print("  ✓ Configuration management")
    print("\nNext Steps:")
    print("  - Try the CLI: python -m graydient_toolkit.toolkit_cli --help")
    print("  - Explore the tutorial system")
    print("  - Build your own workflows!")


if __name__ == "__main__":
    main()
