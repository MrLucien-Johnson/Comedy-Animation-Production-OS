"""Canon creation prompts — family-friendly fictional cartoon locks."""

from __future__ import annotations

STYLE_MASTER_PROMPT = """
professional original 2D cartoon illustration, warm family comedy animation,
Caribbean/Jamaican-inspired environment atmosphere, bold clean dark outlines,
flat/cel shading, warm earthy colours, simple readable silhouettes,
expressive facial language, subtle analogue/paper texture,
animation-friendly construction, consistent line weight, clean composition.
STYLE MASTER reference only — establish visual language for a fictional series,
NOT a definitive character design sheet for Likkle Jay.
Square 1:1. Fictional animated cartoon only.
No photorealism, photography, 3D CGI, anime/manga styling.
No text, letters, logos, watermarks, or signatures.
""".strip()

STYLE_NEGATIVE = """
photorealistic, photography, live action, 3d render, cgi, anime, manga,
hyper detailed, complex lighting, text, letters, watermark, logo, signature,
NSFW, gore, celebrity likeness
""".strip()

# Deterministic seeds permanently bound to style-master candidate slots
STYLE_MASTER_SEEDS: dict[str, int] = {
    "style-master-candidate-001": 305011,
    "style-master-candidate-002": 305022,
    "style-master-candidate-003": 305033,
}

PROMPT_COMPILER_VERSION = "capos-style-master-v2"

LIKKLE_JAY_MASTER_PROMPT = """
Fictional male cartoon character MASTER reference. Young character design.
Medium/dark brown skin. Round youthful face with rounded cheeks.
HAIR HARD LOCK: rounded dome of tight black curls, full and consistent; deep black; dense;
tight curls; rounded dome silhouette; short-to-medium; natural curved perimeter.
NEVER: fade, taper, crop differently, flatten, slick, straighten, loosen curl pattern,
change hair length.
OUTFIT: yellow T-shirt with red collar trim and green shorts.
Neutral pose, front or slight three-quarter, full body, clear silhouette, minimal obstruction,
clean reference background suitable for turnaround locking.
Fictional family-friendly 2D cartoon matching approved series style. No text or watermark.
""".strip()

AUNTIE_BEV_MASTER_PROMPT = """
Fictional female cartoon character MASTER reference.
Medium/dark brown skin. Rounded/stout silhouette.
Orange/red floral house dress with matching patterned headwrap.
Round glasses. Gold earrings.
Neutral pose, front or slight three-quarter, full body, clear silhouette,
clean reference background.
Fictional family-friendly 2D cartoon matching approved series style. No text or watermark.
""".strip()

KITCHEN_EMPTY_PROMPT = """
EMPTY kitchen LOCATION MASTER. No characters.
Warm beige/orange walls, terracotta/brown tiled floor, wooden cabinets with round handles,
beige/light brown countertop.
COUNTER on LEFT. Cream/off-white REFRIGERATOR on RIGHT.
Straight-on cartoon camera baseline. Do not mirror the room.
Fictional family-friendly 2D cartoon interior. No people. No text or watermark.
""".strip()

LIVING_ROOM_EMPTY_PROMPT = """
EMPTY living room LOCATION MASTER. No characters.
Warm brown/orange sofa with patterned cushions, wooden coffee table, warm beige walls,
family-friendly decorative details, window with daylight, warm palette.
Straight-on establishing camera. Fictional 2D cartoon. No text or watermark.
""".strip()

YARD_EMPTY_PROMPT = """
EMPTY residential yard LOCATION MASTER. No characters.
Warm Jamaican/Caribbean residential yard, green vegetation, fence,
banana/tropical planting where appropriate, recognisable house exterior, sunny warm palette.
Straight-on exterior baseline. Fictional 2D cartoon. No text or watermark.
""".strip()

BEDROOM_EMPTY_PROMPT = """
EMPTY Likkle Jay bedroom LOCATION MASTER. No characters.
Simple bed with colourful blanket, dresser/toy shelf, window, warm palette.
Must visually belong to the same house/world as other location masters.
Straight-on bedroom baseline. Fictional 2D cartoon. No text or watermark.
""".strip()

COOKIE_JAR_PROMPT = """
Standalone COOKIE JAR prop MASTER on a clean simple background.
Transparent glass jar with rounded lid. Small golden-brown cookies inside (proportionate —
NOT oversized). Leave the jar LABEL AREA blank/plain — text will be composited later as
exactly COOKIES. Do not render any letters. Fictional 2D cartoon prop matching series style.
""".strip()

GOLDEN_F03_PROMPT = """
Season 1 Episode 2 Di Cookie Jar — Frame 3 transition. NO SPEECH. NO TEXT.
Likkle Jay sneaking/taking a cookie from an OPEN cookie jar on the LEFT COUNTER.
Lid OFF, resting beside the jar. Kitchen matches approved kitchen master geometry
(counter left, fridge right, straight-on). Character matches approved Likkle Jay master
including hair dome lock and yellow shirt/red collar/green shorts.
Fictional family-friendly 2D cartoon. No watermark text in image.
""".strip()


def turnaround_prompt(view: str, character: str) -> str:
    return (
        f"Character TURNAROUND reference view: {view}. "
        f"Same identity as approved {character} master. "
        "Maintain height, body proportions, head size, hair volume/silhouette, skin tone, "
        "outfit geometry and colour palette. Clean reference background. "
        "Do not redefine the master. Fictional 2D cartoon. No text."
    )


def expression_prompt(expression: str, character: str) -> str:
    return (
        f"Character EXPRESSION reference: {expression} for approved {character} master. "
        "Alter facial acting only. Do not redesign clothing, body, hair identity, or background. "
        "Fictional 2D cartoon. No text."
    )


def cookie_state_prompt(state: str) -> str:
    return (
        f"Same approved cookie jar prop identity, STATE={state}. "
        "Do not redesign jar shape, scale, or cookie size. Leave label area blank for "
        "deterministic COOKIES compositing. Fictional 2D cartoon. No letters."
    )
