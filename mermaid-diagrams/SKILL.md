---
name: mermaid-diagrams
description: Comprehensive guide for creating software diagrams using Mermaid syntax. Use when users need to create, visualize, or document software through diagrams including class diagrams (domain modeling, object-oriented design), sequence diagrams (application flows, API interactions, code execution), flowcharts (processes, algorithms, user journeys), entity relationship diagrams (database schemas), C4 architecture diagrams (system context, containers, components), state diagrams, git graphs, pie charts, gantt charts, or any other diagram type. Triggers include requests to "diagram", "visualize", "model", "map out", "show the flow", or when explaining system architecture, database design, code structure, or user/application flows.
---

# Mermaid Diagramming

Create professional software diagrams using Mermaid's text-based syntax. Mermaid renders diagrams from simple text definitions, making diagrams version-controllable, easy to update, and maintainable alongside code.

## Core Syntax Structure

All Mermaid diagrams follow this pattern:

```mermaid
diagramType
  definition content
```

**Key principles:**
- First line declares diagram type (e.g., `classDiagram`, `sequenceDiagram`, `flowchart`)
- Use `%%` for comments
- Line breaks and indentation improve readability but aren't required
- Unknown words break diagrams; parameters fail silently

## Diagram Type Selection Guide

1. **Class Diagrams** - Domain modeling, OOP design, entity relationships
2. **Sequence Diagrams** - API flows, authentication, system component interactions
3. **Flowcharts** - User journeys, business processes, algorithm logic, pipelines
4. **ERD** - Database schemas, table relationships, data modeling
5. **C4 Diagrams** - System context, containers, components, code-level architecture
6. **State Diagrams** - State machines, lifecycle states
7. **Git Graphs** - Branching strategies
8. **Gantt Charts** - Project timelines, scheduling
9. **Pie/Bar Charts** - Data visualization

## Quick Start

각 다이어그램 유형별 예시: `{baseDir}/references/quick-start.md` 참고

## Detailed References

- **`{baseDir}/references/class-diagrams.md`** - Relationships, multiplicity, methods/properties
- **`{baseDir}/references/sequence-diagrams.md`** - Messages, activations, loops, alt/opt/par blocks
- **`{baseDir}/references/flowcharts.md`** - Node shapes, connections, subgraphs, styling
- **`{baseDir}/references/erd-diagrams.md`** - Entities, cardinality, keys, attributes
- **`{baseDir}/references/c4-diagrams.md`** - System context, container, component diagrams
- **`{baseDir}/references/architecture-diagrams.md`** - Cloud, infrastructure, CI/CD
- **`{baseDir}/references/advanced-features.md`** - Themes, styling, configuration, export options

## Best Practices

1. **Start Simple** - Begin with core entities, add details incrementally
2. **Use Meaningful Names** - Clear labels make diagrams self-documenting
3. **Comment Extensively** - Use `%%` comments for complex relationships
4. **Keep Focused** - One diagram per concept; split large diagrams
5. **Version Control** - Store `.mmd` files alongside code
6. **Iterate** - Refine diagrams as understanding evolves

## Common Pitfalls

- **Breaking characters** - Avoid `{}` in comments, escape special characters
- **Syntax errors** - Validate in [Mermaid Live Editor](https://mermaid.live)
- **Overcomplexity** - Split into multiple focused views

## When to Create Diagrams

New projects, complex systems, architecture decisions, DB schemas, refactoring plans, onboarding — 기술적 맥락을 시각화해야 할 때마다 사용하세요.
