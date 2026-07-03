#!/usr/bin/env python3
"""Build BubbleHub docs from Markdown into static HTML."""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
import shutil
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


SITE_URL = "https://bubblehub.ai"
BRAND = "BubbleHub"
BUBBLEHUB_REPO = "bublhub/BubbleHub"
DEFAULT_SOURCE_REF = "main"


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    description: str
    section: str
    kind: str
    source_path: str
    include_sections: list[str] | None = None
    supporting_sources: list[str] | None = None


@dataclass(frozen=True)
class TocItem:
    level: int
    text: str
    anchor: str


@dataclass(frozen=True)
class RenderedMarkdown:
    html: str
    toc: list[TocItem]
    plain_text: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BubbleHub documentation pages.")
    parser.add_argument("--source-dir", default="docs-src", help="Directory containing docs Markdown sources.")
    parser.add_argument("--output-dir", default="docs", help="Directory where generated docs HTML is written.")
    parser.add_argument(
        "--source-ref",
        default=os.environ.get("BUBBLEHUB_DOCS_REF", DEFAULT_SOURCE_REF),
        help="Git ref to fetch from bublhub/BubbleHub.",
    )
    parser.add_argument(
        "--repo-dir",
        default=os.environ.get("BUBBLEHUB_DOCS_REPO_DIR"),
        help="Optional local BubbleHub checkout to read instead of GitHub raw URLs.",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    pages = load_pages(source_dir / "nav.json")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered_pages: dict[str, RenderedMarkdown] = {}
    for page in pages:
        markdown = build_page_markdown(
            page=page,
            pages=pages,
            source_ref=args.source_ref,
            repo_dir=Path(args.repo_dir) if args.repo_dir else None,
        )
        rendered_pages[page.slug] = render_markdown(markdown)

    for index, page in enumerate(pages):
        rendered = rendered_pages[page.slug]
        previous_page = pages[index - 1] if index > 0 else None
        next_page = pages[index + 1] if index + 1 < len(pages) else None
        output_path = page_output_path(output_dir, page)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            render_page(
                page=page,
                pages=pages,
                rendered=rendered,
                previous_page=previous_page,
                next_page=next_page,
            ),
            encoding="utf-8",
        )

    write_search_index(output_dir / "search-index.json", pages, rendered_pages)
    print(f"Built {len(pages)} docs pages in {output_dir}")
    return 0


def load_pages(nav_path: Path) -> list[Page]:
    data = json.loads(nav_path.read_text(encoding="utf-8"))
    return [Page(**item) for item in data]


def build_page_markdown(
    *,
    page: Page,
    pages: list[Page],
    source_ref: str,
    repo_dir: Path | None,
) -> str:
    source = load_source(page.source_path, source_ref=source_ref, repo_dir=repo_dir)

    if page.kind == "index":
        source_markdown = extract_sections(source, page.include_sections or [])
        return "\n\n".join(
            [
                f"# {page.title}",
                source_markdown,
                build_docs_map(pages),
            ]
        )

    if page.kind == "markdown":
        markdown = extract_sections(source, page.include_sections) if page.include_sections else source
        return rewrite_source_links(markdown, source_ref)

    if page.kind == "cli_reference":
        supporting = {
            path: load_source(path, source_ref=source_ref, repo_dir=repo_dir)
            for path in (page.supporting_sources or [])
        }
        return build_cli_reference(source, supporting, source_ref)

    raise ValueError(f"Unknown docs page kind: {page.kind}")


def load_source(path: str, *, source_ref: str, repo_dir: Path | None) -> str:
    if repo_dir is not None:
        return (repo_dir / path).read_text(encoding="utf-8")

    url = raw_github_url(path, source_ref)
    request = Request(url, headers={"User-Agent": "bubblehub-website-docs"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def raw_github_url(path: str, source_ref: str) -> str:
    return f"https://raw.githubusercontent.com/{BUBBLEHUB_REPO}/{quote(source_ref)}/{quote(path)}"


def blob_github_url(path: str, source_ref: str) -> str:
    return f"https://github.com/{BUBBLEHUB_REPO}/blob/{quote(source_ref)}/{quote(path)}"


def extract_sections(markdown: str, section_titles: list[str]) -> str:
    if not section_titles:
        return markdown

    wanted = set(section_titles)
    lines = markdown.splitlines()
    sections: list[str] = []
    index = 0

    while index < len(lines):
        match = re.match(r"^##\s+(.+)$", lines[index])
        if not match:
            index += 1
            continue

        title = strip_markdown(match.group(1)).strip()
        section_lines = [lines[index]]
        index += 1
        while index < len(lines) and not re.match(r"^##\s+.+$", lines[index]):
            section_lines.append(lines[index])
            index += 1

        if title in wanted:
            sections.append("\n".join(section_lines).strip())

    missing = wanted - {strip_markdown(re.match(r"^##\s+(.+)$", section.splitlines()[0]).group(1)).strip() for section in sections}
    if missing:
        raise ValueError(f"Missing sections in source markdown: {', '.join(sorted(missing))}")

    return "\n\n".join(sections)


def build_docs_map(pages: list[Page]) -> str:
    page_lines = ["## Documentation map"]
    for page in pages:
        if page.slug == "index":
            continue
        href = f"/docs/{page.slug}/"
        page_lines.append(f"- [{page.title}]({href}): {page.description}")
    return "\n".join(page_lines)


def rewrite_source_links(markdown: str, source_ref: str) -> str:
    def replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = match.group(2)
        if href.startswith(("http://", "https://", "#", "/", "mailto:")):
            return match.group(0)
        if href == "docs/sandbox.md":
            return f"[{label}](/docs/security/)"
        return f"[{label}]({blob_github_url(href, source_ref)})"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, markdown)


def build_cli_reference(main_source: str, supporting_sources: dict[str, str], source_ref: str) -> str:
    command_names = sorted(set(re.findall(r'\bapp\.command\("([^"]+)"\)', main_source)))
    group_names = sorted(set(re.findall(r'app\.add_typer\([^)]*name="([^"]+)"', main_source)))
    model_commands = extract_decorated_commands(main_source, "models_app")
    specialty_commands = extract_decorated_commands(main_source, "specialties_app")
    run_options = extract_typer_options(supporting_sources.get("bubblehub/cli/run.py", ""))
    shell_options = extract_typer_options(supporting_sources.get("bubblehub/cli/shell.py", ""))
    run_doc = extract_function_docstring(supporting_sources.get("bubblehub/cli/run.py", ""), "command")
    shell_doc = extract_function_docstring(supporting_sources.get("bubblehub/cli/shell.py", ""), "command")

    lines = [
        "# CLI Reference",
        "",
        f"This reference is generated from the BubbleHub source on GitHub at `{source_ref}`.",
        "",
        "## Source files",
        "",
        f"- [`bubblehub/cli/main.py`]({blob_github_url('bubblehub/cli/main.py', source_ref)})",
        f"- [`bubblehub/cli/run.py`]({blob_github_url('bubblehub/cli/run.py', source_ref)})",
        f"- [`bubblehub/cli/shell.py`]({blob_github_url('bubblehub/cli/shell.py', source_ref)})",
        "",
        "## Command surface",
        "",
    ]

    for command in command_names:
        lines.append(f"- `bubblehub {command}`")
    for group in group_names:
        lines.append(f"- `bubblehub {group}`")

    lines.extend(["", "## Model commands", ""])
    for command, description in model_commands:
        suffix = f" {command}" if command else ""
        lines.append(f"- `bubblehub models{suffix}`: {description}")

    if specialty_commands:
        lines.extend(["", "## Specialty commands", ""])
        for command, description in specialty_commands:
            lines.append(f"- `bubblehub specialties {command}`: {description}")

    lines.extend(
        [
            "",
            "## Running agents",
            "",
            run_doc or "Run a binary as a BubbleHub agent inside the hardened sandbox.",
            "",
            "```bash",
            "bubblehub run --root-dir ./workspace --binary ./agent.py --memory 16G",
            "```",
            "",
            "### `bubblehub run` options",
            "",
        ]
    )
    lines.extend(format_options(run_options))

    lines.extend(
        [
            "",
            "## Interactive shells",
            "",
            shell_doc or "Open an interactive BubbleHub sandbox shell.",
            "",
            "```bash",
            "bubblehub shell --name reviewer --root-dir ./workspace",
            "```",
            "",
            "### `bubblehub shell` options",
            "",
        ]
    )
    lines.extend(format_options(shell_options))

    return "\n".join(lines)


def extract_decorated_commands(source: str, typer_name: str) -> list[tuple[str, str]]:
    commands: list[tuple[str, str]] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "command"
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == typer_name
            ):
                command = decorator.args[0].value if decorator.args and isinstance(decorator.args[0], ast.Constant) else ""
                commands.append((command, ast.get_docstring(node) or "See command help."))
    return commands


def extract_function_docstring(source: str, function_name: str) -> str:
    if not source:
        return ""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_docstring(node) or ""
    return ""


def extract_typer_options(source: str) -> list[tuple[str, str]]:
    if not source:
        return []
    tree = ast.parse(source)
    options: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "command":
            continue
        defaults = node.args.defaults
        args = node.args.args[-len(defaults):] if defaults else []
        for arg, default in zip(args, defaults):
            if not (
                isinstance(default, ast.Call)
                and isinstance(default.func, ast.Attribute)
                and default.func.attr == "Option"
            ):
                continue
            flags = [
                item.value
                for item in default.args
                if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value.startswith("--")
            ]
            help_text = ""
            for keyword in default.keywords:
                if keyword.arg == "help" and isinstance(keyword.value, ast.Constant):
                    help_text = str(keyword.value.value)
            if flags:
                options.append((", ".join(f"`{flag}`" for flag in flags), help_text or arg.arg.replace("_", " ")))
    return options


def format_options(options: list[tuple[str, str]]) -> list[str]:
    if not options:
        return ["- Run `--help` for the current option list."]
    return [f"- {flags}: {description}" for flags, description in options]


def page_output_path(output_dir: Path, page: Page) -> Path:
    if page.slug == "index":
        return output_dir / "index.html"

    return output_dir / page.slug / "index.html"


def render_markdown(markdown: str) -> RenderedMarkdown:
    lines = markdown.splitlines()
    html_parts: list[str] = []
    toc: list[TocItem] = []
    plain_parts: list[str] = []
    used_anchors: set[str] = set()
    index = 0

    while index < len(lines):
        line = lines[index]

        if not line.strip():
            index += 1
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            index += 1
            html_parts.append(render_code_block("\n".join(code_lines), language))
            plain_parts.append("\n".join(code_lines))
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            text = strip_markdown(heading.group(2))
            anchor = unique_anchor(slugify(text), used_anchors)
            html_parts.append(f'<h{level} id="{anchor}">{render_inline(text)}</h{level}>')
            if level in (2, 3):
                toc.append(TocItem(level=level, text=text, anchor=anchor))
            plain_parts.append(text)
            index += 1
            continue

        if line.startswith("> "):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].startswith("> "):
                quote_lines.append(lines[index][2:].strip())
                index += 1
            quote_html = " ".join(render_inline(item) for item in quote_lines)
            html_parts.append(f"<blockquote>{quote_html}</blockquote>")
            plain_parts.extend(quote_lines)
            continue

        if re.match(r"^\s*-\s+", line):
            items: list[str] = []
            while index < len(lines) and re.match(r"^\s*-\s+", lines[index]):
                items.append(re.sub(r"^\s*-\s+", "", lines[index]).strip())
                index += 1
            html_parts.append("<ul>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ul>")
            plain_parts.extend(strip_markdown(item) for item in items)
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while index < len(lines) and re.match(r"^\s*\d+\.\s+", lines[index]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[index]).strip())
                index += 1
            html_parts.append("<ol>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ol>")
            plain_parts.extend(strip_markdown(item) for item in items)
            continue

        paragraph_lines: list[str] = []
        while index < len(lines) and is_paragraph_line(lines[index]):
            paragraph_lines.append(lines[index].strip())
            index += 1
        paragraph = " ".join(paragraph_lines)
        html_parts.append(f"<p>{render_inline(paragraph)}</p>")
        plain_parts.append(strip_markdown(paragraph))

    return RenderedMarkdown(
        html="\n".join(html_parts),
        toc=toc,
        plain_text=" ".join(plain_parts),
    )


def is_paragraph_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not (
        stripped.startswith("#")
        or stripped.startswith("```")
        or stripped.startswith("> ")
        or re.match(r"^\s*-\s+", line)
        or re.match(r"^\s*\d+\.\s+", line)
    )


def render_code_block(code: str, language: str) -> str:
    language_label = language or "text"
    language_class = f' class="language-{html.escape(language_label, quote=True)}"'
    escaped_code = html.escape(code)
    return (
        '<div class="docs-code-block">'
        '<div class="docs-code-header">'
        f"<span>{html.escape(language_label)}</span>"
        '<button class="copy-button docs-copy-button" type="button" data-copy-code>Copy</button>'
        "</div>"
        f"<pre><code{language_class}>{escaped_code}</code></pre>"
        "</div>"
    )


def render_inline(text: str) -> str:
    tokens: list[str] = []

    def store_code(match: re.Match[str]) -> str:
        tokens.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"@@CODE{len(tokens) - 1}@@"

    text = re.sub(r"`([^`]+)`", store_code, text)
    escaped = html.escape(text)

    def replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = html.escape(match.group(2), quote=True)
        attrs = ' rel="noreferrer"' if href.startswith("http") else ""
        return f'<a href="{href}"{attrs}>{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    for token_index, value in enumerate(tokens):
        escaped = escaped.replace(f"@@CODE{token_index}@@", value)
    return escaped


def strip_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def unique_anchor(anchor: str, used: set[str]) -> str:
    candidate = anchor
    counter = 2
    while candidate in used:
        candidate = f"{anchor}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def render_page(
    *,
    page: Page,
    pages: list[Page],
    rendered: RenderedMarkdown,
    previous_page: Page | None,
    next_page: Page | None,
) -> str:
    asset_prefix = "../" if page.slug == "index" else "../../"
    docs_prefix = "" if page.slug == "index" else "../"
    canonical_path = "/docs/" if page.slug == "index" else f"/docs/{page.slug}/"
    canonical_url = f"{SITE_URL}{canonical_path}"
    page_title = f"{page.title} | {BRAND} Docs"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{html.escape(page.description, quote=True)}">
    <meta name="theme-color" content="#000000">
    <link rel="canonical" href="{canonical_url}">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="{BRAND} Docs">
    <meta property="og:title" content="{html.escape(page_title, quote=True)}">
    <meta property="og:description" content="{html.escape(page.description, quote=True)}">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:image" content="{SITE_URL}/assets/bubblehub-logo-dark.svg">
    <meta property="og:image:alt" content="BubbleHub logo with three pink bubbles and a white wordmark.">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(page_title, quote=True)}">
    <meta name="twitter:description" content="{html.escape(page.description, quote=True)}">
    <meta name="twitter:image" content="{SITE_URL}/assets/bubblehub-logo-dark.svg">
    <title>{html.escape(page_title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap"
      rel="stylesheet"
    >
    <link rel="icon" href="{asset_prefix}assets/bubblehub-icon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="{asset_prefix}styles.css">
  </head>
  <body>
    <div class="site-shell docs-shell">
      {render_top_nav(asset_prefix, docs_prefix)}
      <main class="docs-page">
        <section class="docs-hero" aria-labelledby="docs-page-title">
          <p class="eyebrow">BubbleHub Docs</p>
          <h1 id="docs-page-title">{html.escape(page.title)}</h1>
          <p class="hero-lede">{html.escape(page.description)}</p>
          <div class="docs-search" role="search">
            <label for="docs-search-input">Search docs</label>
            <input
              id="docs-search-input"
              type="search"
              placeholder="Search commands, guides, and concepts"
              autocomplete="off"
              data-docs-search
              data-search-index="{docs_prefix}search-index.json"
            >
            <div class="docs-search-results" data-docs-search-results hidden></div>
          </div>
        </section>
        <div class="docs-layout">
          <aside class="docs-sidebar" aria-label="Docs navigation">
            {render_sidebar(pages, page, docs_prefix)}
          </aside>
          <article class="docs-content">
            {rendered.html}
            {render_prev_next(previous_page, next_page, docs_prefix)}
          </article>
          {render_toc(rendered.toc)}
        </div>
      </main>
    </div>
    <script src="{asset_prefix}script.js" data-cfasync="false"></script>
  </body>
</html>
"""


def render_top_nav(asset_prefix: str, docs_prefix: str) -> str:
    docs_home_href = docs_prefix or "./"
    return f"""
      <header class="nav">
        <a class="brand" href="{asset_prefix}" aria-label="BubbleHub home">
          <img class="brand-mark" src="{asset_prefix}assets/bubblehub-icon.svg" alt="" width="34" height="34">
          <span>BubbleHub</span>
        </a>
        <nav class="nav-links" aria-label="Primary navigation">
          <a href="{docs_home_href}">Docs</a>
          <a href="{asset_prefix}#enterprise">Enterprise</a>
          <a class="icon-link" href="https://github.com/bublhub/BubbleHub" rel="noreferrer">
            <svg class="link-icon" aria-hidden="true" viewBox="0 0 16 16">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012 8.012 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
            GitHub
          </a>
          <a class="icon-link" href="https://discord.gg/skwKqSgvD2" rel="noreferrer">
            <svg class="link-icon" aria-hidden="true" viewBox="0 0 24 24">
              <path d="M19.54 5.32A17.2 17.2 0 0 0 15.31 4l-.2.38c-.24.45-.45.92-.63 1.4a15.88 15.88 0 0 0-4.96 0 10.5 10.5 0 0 0-.83-1.78 17.1 17.1 0 0 0-4.24 1.32C1.76 9.36 1.03 13.3 1.4 17.17A17.28 17.28 0 0 0 6.59 20c.42-.58.79-1.19 1.1-1.84a10.9 10.9 0 0 1-1.73-.84l.43-.34a12.38 12.38 0 0 0 11.22 0l.43.34c-.55.33-1.13.61-1.74.84.32.65.69 1.26 1.1 1.84a17.23 17.23 0 0 0 5.2-2.83c.44-4.49-.75-8.4-3.06-11.85ZM8.68 14.78c-1 0-1.82-.94-1.82-2.1 0-1.15.8-2.1 1.82-2.1 1.01 0 1.83.95 1.82 2.1 0 1.16-.8 2.1-1.82 2.1Zm6.64 0c-1 0-1.82-.94-1.82-2.1 0-1.15.8-2.1 1.82-2.1 1.01 0 1.83.95 1.82 2.1 0 1.16-.8 2.1-1.82 2.1Z" />
            </svg>
            Discord
          </a>
        </nav>
        <a class="button button-small" href="{asset_prefix}download/">Download</a>
      </header>
"""


def render_sidebar(pages: list[Page], current_page: Page, docs_prefix: str) -> str:
    sections: dict[str, list[Page]] = {}
    for page in pages:
        sections.setdefault(page.section, []).append(page)

    parts: list[str] = []
    for section, section_pages in sections.items():
        parts.append(f'<div class="docs-nav-section"><h2>{html.escape(section)}</h2><ol>')
        for page in section_pages:
            href = page_href(page, docs_prefix)
            current = ' aria-current="page"' if page.slug == current_page.slug else ""
            active_class = " class=\"is-active\"" if page.slug == current_page.slug else ""
            parts.append(f'<li><a{active_class}{current} href="{href}">{html.escape(page.title)}</a></li>')
        parts.append("</ol></div>")
    return "\n".join(parts)


def page_href(page: Page, docs_prefix: str) -> str:
    if page.slug == "index":
        return docs_prefix or "./"

    return f"{docs_prefix}{page.slug}/"


def render_toc(toc: list[TocItem]) -> str:
    if not toc:
        return '<aside class="docs-toc" aria-label="On this page"></aside>'

    links = "\n".join(
        f'<li class="toc-level-{item.level}"><a href="#{item.anchor}">{html.escape(item.text)}</a></li>'
        for item in toc
    )
    return f"""
          <aside class="docs-toc" aria-label="On this page">
            <h2>On this page</h2>
            <ol>
              {links}
            </ol>
          </aside>
"""


def render_prev_next(previous_page: Page | None, next_page: Page | None, docs_prefix: str) -> str:
    links: list[str] = []
    if previous_page:
        links.append(
            f'<a class="docs-prev" href="{page_href(previous_page, docs_prefix)}">'
            f"<span>Previous</span>{html.escape(previous_page.title)}</a>"
        )
    if next_page:
        links.append(
            f'<a class="docs-next" href="{page_href(next_page, docs_prefix)}">'
            f"<span>Next</span>{html.escape(next_page.title)}</a>"
        )

    if not links:
        return ""

    return '<nav class="docs-pagination" aria-label="Docs pagination">' + "".join(links) + "</nav>"


def write_search_index(path: Path, pages: list[Page], rendered_pages: dict[str, RenderedMarkdown]) -> None:
    entries = []
    for page in pages:
        href = "/docs/" if page.slug == "index" else f"/docs/{page.slug}/"
        rendered = rendered_pages[page.slug]
        entries.append(
            {
                "title": page.title,
                "description": page.description,
                "href": href,
                "section": page.section,
                "text": rendered.plain_text[:5000],
            }
        )

    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
