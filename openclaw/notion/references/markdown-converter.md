# Markdown Converter

The skill includes a markdown-to-Notion-blocks converter for easy content creation from markdown files.

**Why needed:** Notion's API requires structured block objects (JSON). Writing these manually is verbose and error-prone, especially for formatted content.

## Usage

```python
from skills.notion.markdown_converter import markdown_to_blocks
from skills.notion.client import NotionClient

# Convert markdown to Notion blocks
markdown = """
# Main Title

This is a **bold** paragraph with *italic* text.

## Section 1

- Bullet point 1
- Bullet point 2

```python
def hello():
    print("Hello!")
```
"""

blocks = markdown_to_blocks(markdown)

# Append to Notion page
notion = NotionClient()
notion.append_blocks(page_id, blocks)
```

## Supported Markdown Elements

| Markdown | Notion Block | Notes |
|----------|--------------|-------|
| `# H1`, `## H2`, `### H3` | `heading_1`, `heading_2`, `heading_3` | H4-H6 map to heading_3 |
| `- item` or `* item` | `bulleted_list_item` | |
| `1. item`, `2. item` | `numbered_list_item` | |
| ` ```language` | `code` block | Syntax highlighting |
| `**bold**`, `*italic*` | Inline annotations | |
| `` `code` `` | Inline code | |
| `[text](url)` | Link | |
| `> quote` | `callout` | Rendered with icon |
| `---` | `divider` | |

## Batch Processing for Large Documents

Notion limits block operations to 100 blocks per request. For longer documents, use batching:

```python
blocks = markdown_to_blocks(long_markdown)

# Append in batches of 100
for i in range(0, len(blocks), 100):
    batch = blocks[i:i+100]
    notion.append_blocks(page_id, batch)
    print(f"Appended blocks {i+1}-{min(i+100, len(blocks))}")
```

## When to Use

**Use markdown converter when:**
- Creating documentation pages from markdown files
- Importing blog posts or READMEs to Notion
- Automating content creation with formatted text

**Don't use when:**
- Content is already in Notion's block format
- You need advanced block types (tables, embeds, databases)
- Real-time collaboration/editing is needed (use Notion UI)

## Limitations & Future Improvements

**Current limitations:**
- No table support (Notion tables are complex)
- Nested lists are flattened (no indentation)
- No image parsing (`![alt](url)`)
- No strikethrough (`~~text~~`) or underline

**Planned features:**
- Image block support
- Nested list indentation
- Table parsing
- More inline styles
