# Felt Agent Skill

An agent skill for working with Felt Maps, web-based GIS software.

## Overview

This skill enables Claude Code agents to effectively work with Felt using the `felt-python` library and FSL (Felt Style Language). It provides comprehensive guidance on:

- **felt-python library**: Authentication, map creation, data upload, layer management
- **FSL (Felt Style Language)**: JSON-based styling for map layers with examples
- **GIS Data Sources**: Curated list of free, high-quality GIS data sources

### Installation

```bash
mkdir -p ~/.claude/skills
git clone git@github.com:felt/skills.git ~/.claude/skills/felt
```

## Usage

* Go create a new Felt API key for Claude to use (easy to delete later for security reasons)

* Create a new Claude Code project

```
mkdir my-project
cd my-project
claude 
> Make me a pretty earthquake map
```

Dangerous Tip: use `claude --dangerously-skip-permissions` if you don't want to get prompted for permissions over and over

## Skill Contents

The skill automatically activates when you ask about:
- Creating Felt maps
- Uploading GIS data
- Styling map features with FSL
- Finding GIS datasets
- Working with felt-python library

### Core Topics

1. **Installation & Authentication**
   - Installing felt-python
   - API token setup

2. **Map Operations**
   - Creating maps with coordinates
   - Map access levels

3. **Data Upload**
   - Files (GeoJSON, Shapefiles, CSV, KML)
   - Pandas DataFrames
   - GeoPandas GeoDataFrames
   - Layer refresh operations

4. **FSL Styling**
   - Simple visualizations
   - Categorical styling
   - Numeric visualizations
   - Heatmaps
   - Paint properties
   - Label configuration

5. **GIS Data Sources**
   - Global vector data (Natural Earth, OpenStreetMap)
   - Government sources (USGS, US Census)
   - Administrative boundaries (GADM, DIVA-GIS)
   - Open data portals

## Resources

- [felt-python GitHub](https://github.com/felt/felt-python)
- [Felt Developer Documentation](https://developers.felt.com)
- [FSL Getting Started](https://developers.felt.com/felt-style-language/getting-started)
- [FSL Examples](https://developers.felt.com/felt-style-language/examples)
