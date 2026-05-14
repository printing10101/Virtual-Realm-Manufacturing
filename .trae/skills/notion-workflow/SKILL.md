---
name: "notion-workflow"
description: "Complete Notion workspace integration. Invoke when working with Notion pages, databases, workers, API calls, knowledge capture, meeting intelligence, research documentation, or spec-to-implementation tasks."
---

# Notion Workflow

Complete Notion workspace skill combining CLI operations, knowledge capture, meeting intelligence, research documentation, and spec-to-implementation workflows.

## Core Capabilities

### 1. CLI Operations (`ntn`)

**Authentication:**
- `NOTION_API_TOKEN` — required for `ntn api` and `ntn files`
- `ntn login` / `ntn logout` — session auth for workers/tokens

**API Operations:**
```bash
ntn api ls                          # List all public API endpoints
ntn api <path> --help               # Show methods, docs, usage
ntn api <path> --docs               # Print full official docs
ntn api <path> --spec               # Print OpenAPI fragment
ntn api v1/users page_size==100     # GET with query
ntn api v1/pages parent[page_id]=abc123  # POST with fields
ntn api v1/pages -d '{"parent":{"page_id":"abc123"}}'  # POST JSON
```

**File Operations:**
```bash
ntn files create < image.png                     # Upload file
ntn files create --external-url https://...      # Upload from URL
ntn files list                                   # List uploaded files
ntn files get <upload-id>                        # Get file details
```

**Worker Management:**
```bash
ntn workers new my-worker    # Scaffold new project
ntn workers deploy           # Deploy from current directory
ntn workers ls               # List workers
ntn workers exec <capability>  # Execute capability
```

**Token Management:**
```bash
ntn tokens create
ntn tokens ls
ntn tokens revoke <token-id>
```

### 2. Knowledge Capture

Transform conversations and discussions into structured documentation pages in Notion:
- Captures insights, decisions, and knowledge from chat context
- Formats appropriately for wikis or databases
- Saves with proper organization and linking for easy discovery

**When to use:** User wants to capture knowledge, save decisions, or create wiki entries.

### 3. Meeting Intelligence

Prepares meeting materials by gathering context from Notion, enriching with research, and creating both internal pre-reads and external agendas:
- Pre-meeting: Gather context from related Notion pages
- Enrich with external research if needed
- Create internal pre-read document
- Create external agenda document
- Save both to Notion with proper organization

**When to use:** User needs to prepare for meetings, create agendas, or compile meeting materials.

### 4. Research Documentation

Searches across Notion workspace, synthesizes findings from multiple pages, and creates comprehensive research documentation:
- Searches across workspace for relevant information
- Synthesizes findings from multiple pages
- Creates structured reports with citations
- Saves as new Notion pages with actionable insights

**When to use:** User needs to research topics, compile information, or create comprehensive reports from workspace data.

### 5. Spec-to-Implementation

Turns product or tech specs into concrete Notion tasks for implementation:
- Breaks down spec pages into detailed implementation plans
- Creates clear tasks with acceptance criteria
- Sets up progress tracking
- Guides development from requirements to completion

**When to use:** User has a spec and needs to convert it to actionable implementation tasks.

## Workflow Integration

### Complete Research-to-Implementation Flow:

1. **Research** → Use research documentation to gather information
2. **Meeting** → Create meeting docs to discuss findings
3. **Knowledge** → Capture decisions and insights
4. **Spec** → Convert specs to implementation tasks
5. **CLI** → Deploy workers, manage files, call APIs

## Best Practices

- Always run `ntn api <path> --help` before making API calls
- Use `--docs` to understand full API capabilities
- Keep workers organized with clear naming conventions
- Save all documentation with proper tags and relationships
- Use databases for structured knowledge, pages for narrative content

## Common Triggers

- "Call Notion API"
- "Deploy a worker"
- "Upload file to Notion"
- "Create a page"
- "Query a database"
- "Capture knowledge"
- "Prepare meeting materials"
- "Research in Notion"
- "Convert spec to tasks"
