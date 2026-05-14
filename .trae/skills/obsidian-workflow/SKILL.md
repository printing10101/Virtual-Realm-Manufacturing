---
name: "obsidian-workflow"
description: "Complete Obsidian workspace integration. Invoke when working with Obsidian vaults, notes, tasks, properties, Bases, markdown syntax, wikilinks, callouts, or plugin/theme development."
---

# Obsidian Workflow

Complete Obsidian workspace skill combining CLI operations, Markdown syntax, and Bases database management.

## Core Capabilities

### 1. CLI Operations (`obs`)

**Note Management:**
```bash
obs notes read "Note Name"           # Read a note
obs notes create "New Note"          # Create a note
obs notes search "query"             # Search vault
obs notes list                       # List all notes
obs notes move "Old" "New"           # Rename/move note
obs notes delete "Note"              # Delete note
```

**Task Management:**
```bash
obs tasks list                       # List all tasks
obs tasks create "Task description"  # Create task
obs tasks complete "Task"            # Mark complete
obs tasks search "query"             # Search tasks
```

**Properties Management:**
```bash
obs properties get "Note"            # Get note properties
obs properties set "Note" key value  # Set property
obs properties list "Note"           # List all properties
```

**Plugin Development:**
```bash
obs plugins reload                   # Reload plugins
obs plugins run-javascript "code"    # Run JS in Obsidian
obs plugins capture-errors           # Capture plugin errors
obs plugins inspect-dom              # Inspect DOM
```

**Theme Development:**
```bash
obs themes reload                    # Reload themes
obs themes preview                   # Preview theme
obs themes inspect-css               # Inspect CSS
```

### 2. Markdown Syntax (Obsidian Flavored)

**Wikilinks:**
```markdown
[[Note Name]]                    # Link to note
[[Note Name|Display Text]]       # Link with custom text
[[Note Name#Heading]]            # Link to heading
[[Note Name#^block-id]]          # Link to block
```

**Embeds:**
```markdown
![[Image.png]]                   # Embed image
![[Note Name]]                   # Embed note
![[Note Name#Heading]]           # Embed heading
![[Note Name#^block-id]]         # Embed block
```

**Callouts:**
```markdown
> [!note]
> Note content

> [!tip]
> Tip content

> [!warning]
> Warning content

> [!danger]
> Danger content

> [!info] Title
> Custom title callout
```

**Frontmatter:**
```yaml
---
title: Note Title
tags: [tag1, tag2]
date: 2024-01-01
aliases: [Alternative Name]
cssclasses: [custom-class]
---
```

**Tags:**
```markdown
#tag                           # Simple tag
#parent/child                  # Nested tag
#tag-with-dashes               # Tag with dashes
```

**Dataview Queries:**
```markdown
```dataview
TABLE file.name AS "Note", date
FROM #tag
WHERE date >= date(today) - dur(7 days)
SORT date DESC
```
```

### 3. Bases Database Management

**Create Bases (.base files):**
```markdown
---
name: Project Tracker
type: base
views:
  - type: table
    filters:
      - field: status
        operator: is
        value: active
    columns:
      - field: name
      - field: status
      - field: date
  - type: card
    groupBy: status
formulas:
  - name: Days Remaining
    expression: dateEnd - dateToday
---
```

**Views:**
- **Table**: Spreadsheet-like grid with filters and sorting
- **Card**: Kanban-style boards with grouping
- **List**: Simple list view with custom formatting
- **Calendar**: Date-based organization

**Filters:**
```yaml
filters:
  - field: status
    operator: is
    value: active
  - field: priority
    operator: in
    value: [high, critical]
```

**Formulas:**
```yaml
formulas:
  - name: Days Overdue
    expression: dateToday - dateDue
  - name: Progress
    expression: completed / total * 100
```

**Summaries:**
```yaml
summaries:
  - type: count
    field: tasks
    groupBy: status
  - type: sum
    field: hours
    groupBy: assignee
```

## Workflow Integration

### Note Creation Flow:
1. Use CLI to create note structure
2. Apply Obsidian Markdown syntax
3. Add wikilinks and embeds for connections
4. Set properties and tags for organization
5. Create Bases views if database needed

### Plugin Development Flow:
1. Use CLI to scaffold plugin
2. Test with `obs plugins run-javascript`
3. Debug with `obs plugins capture-errors`
4. Inspect DOM for UI issues
5. Reload and iterate

## Best Practices

- Use wikilinks over markdown links for internal connections
- Keep frontmatter consistent across similar notes
- Use tags for broad categories, wikilinks for specific connections
- Name Bases views descriptively for easy discovery
- Use callouts for important information hierarchy
- Leverage Dataview for dynamic note lists

## Common Triggers

- "Create Obsidian note"
- "Search vault"
- "Add wikilink"
- "Create callout"
- "Set up database"
- "Create Bases view"
- "Develop Obsidian plugin"
- "Inspect DOM"
- "Run JavaScript in Obsidian"
- "Manage tasks"
- "Set properties"
