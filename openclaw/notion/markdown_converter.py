#!/usr/bin/env python3
"""
Markdown to Notion Blocks Converter

Converts markdown text to Notion block objects for proper formatting.

Supports:
- Headings (# - ######)
- Lists (bulleted, numbered)
- Code blocks (with language tags)
- Blockquotes/Callouts
- Bold, italic, code inline formatting
- Links

Usage:
    from skills.notion.markdown_converter import markdown_to_blocks
    
    blocks = markdown_to_blocks(markdown_text)
    notion.append_blocks(page_id, blocks)
"""

import re
from typing import List, Dict, Any, Optional


def markdown_to_blocks(markdown: str, max_blocks: int = 100) -> List[Dict[str, Any]]:
    """
    Convert markdown text to Notion block objects
    
    Args:
        markdown: Markdown text to convert
        max_blocks: Maximum number of blocks (Notion limit is 100 per request)
    
    Returns:
        List of Notion block objects ready for append_blocks()
    
    Example:
        markdown = '''
        # Heading 1
        Some **bold** and *italic* text.
        
        ## Heading 2
        - Bullet 1
        - Bullet 2
        
        1. Numbered 1
        2. Numbered 2
        
        ```python
        print("Hello")
        ```
        '''
        
        blocks = markdown_to_blocks(markdown)
        # Returns Notion block objects
    """
    lines = markdown.split('\n')
    blocks = []
    
    i = 0
    while i < len(lines) and len(blocks) < max_blocks:
        line = lines[i]
        
        # Skip empty lines
        if not line.strip():
            i += 1
            continue
        
        # Code block (```language)
        if line.strip().startswith('```'):
            code_block, consumed = _parse_code_block(lines[i:])
            if code_block:
                blocks.append(code_block)
                i += consumed
                continue
        
        # Headings (# - ######)
        heading_block = _parse_heading(line)
        if heading_block:
            blocks.append(heading_block)
            i += 1
            continue
        
        # Numbered list (1. 2. etc)
        if re.match(r'^\d+\.\s+', line):
            blocks.append(_parse_list_item(line, 'numbered_list_item'))
            i += 1
            continue
        
        # Bulleted list (- or *)
        if re.match(r'^[-*]\s+', line):
            blocks.append(_parse_list_item(line, 'bulleted_list_item'))
            i += 1
            continue
        
        # Blockquote (>)
        if line.strip().startswith('>'):
            blocks.append(_parse_blockquote(line))
            i += 1
            continue
        
        # Divider (---)
        if re.match(r'^-{3,}$', line.strip()):
            blocks.append({"type": "divider", "divider": {}})
            i += 1
            continue
        
        # Default: paragraph
        blocks.append(_parse_paragraph(line))
        i += 1
    
    return blocks


def _parse_heading(line: str) -> Optional[Dict[str, Any]]:
    """Parse markdown heading to Notion heading block"""
    match = re.match(r'^(#{1,6})\s+(.+)$', line)
    if not match:
        return None
    
    level = len(match.group(1))
    text = match.group(2)
    
    # Notion supports heading_1, heading_2, heading_3
    # Map h4-h6 to heading_3
    if level > 3:
        level = 3
    
    heading_type = f"heading_{level}"
    
    return {
        "type": heading_type,
        heading_type: {
            "rich_text": _parse_inline_formatting(text),
            "color": "default",
            "is_toggleable": False
        }
    }


def _parse_paragraph(line: str) -> Dict[str, Any]:
    """Parse plain text to Notion paragraph block"""
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": _parse_inline_formatting(line),
            "color": "default"
        }
    }


def _parse_list_item(line: str, item_type: str) -> Dict[str, Any]:
    """Parse list item (bulleted or numbered)"""
    # Remove list marker (-, *, or 1.)
    if item_type == 'bulleted_list_item':
        text = re.sub(r'^[-*]\s+', '', line)
    else:  # numbered_list_item
        text = re.sub(r'^\d+\.\s+', '', line)
    
    return {
        "type": item_type,
        item_type: {
            "rich_text": _parse_inline_formatting(text),
            "color": "default"
        }
    }


def _parse_code_block(lines: List[str]) -> tuple[Optional[Dict[str, Any]], int]:
    """
    Parse code block (```language ... ```)
    
    Returns:
        (block_object, lines_consumed)
    """
    if not lines[0].strip().startswith('```'):
        return None, 0
    
    # Extract language
    first_line = lines[0].strip()
    language = first_line[3:].strip() or "plain text"
    
    # Find closing ```
    code_lines = []
    i = 1
    while i < len(lines):
        if lines[i].strip() == '```':
            # Found closing marker
            code_text = '\n'.join(code_lines)
            block = {
                "type": "code",
                "code": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": code_text}
                        }
                    ],
                    "language": _normalize_language(language),
                    "caption": []
                }
            }
            return block, i + 1
        
        code_lines.append(lines[i])
        i += 1
    
    # No closing marker found, treat as paragraph
    return None, 0


def _parse_blockquote(line: str) -> Dict[str, Any]:
    """Parse blockquote (>) to Notion callout block"""
    text = re.sub(r'^>\s*', '', line)
    
    return {
        "type": "callout",
        "callout": {
            "rich_text": _parse_inline_formatting(text),
            "icon": {"type": "emoji", "emoji": "💡"},
            "color": "gray_background"
        }
    }


def _parse_inline_formatting(text: str) -> List[Dict[str, Any]]:
    """
    Parse inline markdown formatting (bold, italic, code, links)
    
    Supports:
    - **bold** or __bold__
    - *italic* or _italic_
    - `code`
    - [link text](url)
    
    Returns:
        List of Notion rich_text objects
    """
    rich_text = []
    
    # Pattern: match **bold**, *italic*, `code`, [link](url)
    # Use a simple regex-based approach for basic formatting
    
    # For simplicity, we'll use a basic splitter and create text segments
    # A more robust implementation would use a proper markdown parser
    
    # Split by bold (**text**)
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    
    for part in parts:
        if not part:
            continue
        
        # Check if this is a bold segment
        bold_match = re.match(r'^\*\*(.+)\*\*$', part)
        if bold_match:
            rich_text.append({
                "type": "text",
                "text": {"content": bold_match.group(1)},
                "annotations": {
                    "bold": True,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default"
                }
            })
            continue
        
        # Check for italic (*text* or _text_)
        italic_match = re.match(r'^[*_](.+?)[*_]$', part)
        if italic_match:
            rich_text.append({
                "type": "text",
                "text": {"content": italic_match.group(1)},
                "annotations": {
                    "bold": False,
                    "italic": True,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default"
                }
            })
            continue
        
        # Check for inline code (`text`)
        code_match = re.match(r'^`(.+?)`$', part)
        if code_match:
            rich_text.append({
                "type": "text",
                "text": {"content": code_match.group(1)},
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": True,
                    "color": "default"
                }
            })
            continue
        
        # Check for links ([text](url))
        link_match = re.match(r'^\[(.+?)\]\((.+?)\)$', part)
        if link_match:
            rich_text.append({
                "type": "text",
                "text": {
                    "content": link_match.group(1),
                    "link": {"url": link_match.group(2)}
                },
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default"
                }
            })
            continue
        
        # Plain text (no formatting)
        if part.strip():
            rich_text.append({
                "type": "text",
                "text": {"content": part},
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default"
                }
            })
    
    # Fallback: if no rich_text parsed, return plain text
    if not rich_text:
        return [
            {
                "type": "text",
                "text": {"content": text},
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default"
                }
            }
        ]
    
    return rich_text


def _normalize_language(lang: str) -> str:
    """Normalize language identifier to Notion-supported language"""
    # Notion supported languages: https://developers.notion.com/reference/block#code
    lang_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "sh": "shell",
        "bash": "shell",
        "yml": "yaml",
        "md": "markdown",
        "rb": "ruby",
    }
    
    lang = lang.lower().strip()
    return lang_map.get(lang, lang)


# Example usage and tests
if __name__ == "__main__":
    # Test markdown
    markdown_sample = """
# Main Title

This is a **bold** paragraph with *italic* text and `inline code`.

## Section 1

- Bullet point 1
- Bullet point 2 with **bold**

### Subsection

1. First item
2. Second item

```python
def hello():
    print("Hello, World!")
```

> This is a blockquote

---

Another paragraph with a [link](https://example.com).
"""
    
    blocks = markdown_to_blocks(markdown_sample)
    
    print(f"Generated {len(blocks)} blocks:")
    for i, block in enumerate(blocks):
        print(f"{i+1}. {block['type']}")
