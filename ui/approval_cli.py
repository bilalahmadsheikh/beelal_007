"""
approval_cli.py — BilalAgent v2.0 CLI Approval Interface
Temporary CLI-based approval for content before submission.
NOTE: Will be REPLACED by Chrome Extension overlay in Phase 4.
"""

import sys
import os
import textwrap


def show_approval(content_type: str, content: str) -> str | None:
    """
    Show content to user for approval via CLI.
    
    Args:
        content_type: Type of content (e.g. 'linkedin_post', 'cover_letter', 'gig_description')
        content: The generated content to review
        
    Returns:
        'approved' if approved, 'edit' if user wants to edit, None if cancelled
    """
    print("\n" + "═" * 60)
    print(f"  CONTENT REVIEW — {content_type.upper().replace('_', ' ')}")
    print("═" * 60)
    
    # Display content with word wrap
    print()
    if isinstance(content, dict):
        import json
        print(json.dumps(content, indent=2))
    else:
        for line in content.split('\n'):
            wrapped = textwrap.fill(line, width=70) if line.strip() else ""
            print(wrapped)
    
    # Word count
    if isinstance(content, str):
        word_count = len(content.split())
        char_count = len(content)
        print(f"\n  [{word_count} words | {char_count} chars]")
    
    print("\n" + "─" * 60)
    print("  [A]pprove    [E]dit    [C]ancel")
    print("─" * 60)
    
    while True:
        try:
            choice = input("  Your choice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        
        if choice in ('a', 'approve'):
            print("  ✓ Content approved")
            return 'approved'
        elif choice in ('e', 'edit'):
            print("  ✎ Edit mode — paste your edited version below.")
            print("    (Type 'DONE' on a new line when finished)")
            lines = []
            try:
                while True:
                    line = input()
                    if line.strip().upper() == 'DONE':
                        break
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                return None
            
            edited = '\n'.join(lines)
            if edited.strip():
                print(f"\n  ✓ Edited content accepted ({len(edited.split())} words)")
                return edited
            else:
                print("  Empty edit — showing original again")
                continue
        elif choice in ('c', 'cancel'):
            print("  ✗ Content cancelled")
            return None
        else:
            print("  Invalid choice. Press A, E, or C.")


def auto_approve(content_type: str, content: str) -> str:
    """
    Auto-approve content (for non-interactive / testing mode).
    Just logs and returns the content.
    """
    if isinstance(content, str):
        print(f"[AUTO-APPROVE] {content_type}: {len(content.split())} words")
    else:
        print(f"[AUTO-APPROVE] {content_type}: dict content")
    return 'approved'


if __name__ == "__main__":
    # Test
    sample = """Just shipped basepy-sdk — a Python SDK for Base L2 blockchain.

The result? 40% faster than Web3.py for transaction processing.

Built with Python, AsyncIO, and a lot of late nights.

What started as a semester project turned into something I'm genuinely proud of.

#Python #Web3 #Blockchain #BaseSide #BuildInPublic"""
    
    result = show_approval("linkedin_post", sample)
    print(f"\nResult: {result}")
