#!/usr/bin/env python3
"""Bootstrap Likkle Jay canon registry metadata (no image claims)."""

from __future__ import annotations

import json

from capos.canon.bootstrap import bootstrap_likkle_jay_canon

if __name__ == "__main__":
    print(json.dumps(bootstrap_likkle_jay_canon(), indent=2))
