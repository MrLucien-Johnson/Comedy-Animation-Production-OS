# Reference System

## Canonical assets

Versioned IDs, e.g.:

- `character-likkle-jay-v1`  
- `character-auntie-bev-v1`  
- `location-kitchen-v1`  
- `prop-cookie-jar-v1`  

## Rules

- Generated frames **must** reference canonical asset IDs.  
- Never silently overwrite an approved/locked canonical asset.  
- Create a new version (`create_new_version`) and mark the prior asset `SUPERSEDED`.  

## Store API

`ReferenceStore` in `src/capos/references/versioning.py`:

- `register` / `approve` / `lock_as_canon` / `create_new_version` / `resolve_governing_refs`

## Hierarchy

SERIES → CHARACTER → TURNAROUND / EXPRESSION / OUTFIT → LOCATION MASTER → PROP MASTER → EPISODE / SCENE / SHOT references.
