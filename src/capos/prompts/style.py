"""Visual style and negative constraints for CAPOS comedy animation."""

BASE_STYLE = """
VISUAL STYLE (LOCKED):
Warm-toned family-friendly fictional 2D cartoon.
Bold dark outlines.
Flat shading.
Slight warm/vintage texture.
Expressive faces.
Detailed enough to establish location while remaining suitable for simple animation.
Square 1:1 master frames unless export reframing metadata says otherwise.
Characters and environments are fictional animated designs.
""".strip()

FAMILY_FRIENDLY = """
CONTENT SAFETY:
Fictional animated cartoon scene.
Family-friendly comedy.
No photorealistic people.
Do not depict real individuals.
""".strip()

NO_BAKED_TEXT = """
TEXT POLICY:
Do not render speech-bubble lettering, titles, captions, or watermarks in the image.
Leave clean space for programmatic speech bubbles if dialogue is indicated.
Watermark and dialogue are composited in post with exact spelling.
""".strip()

NEGATIVE_CONSTRAINTS = """
photorealistic, live action, real person, deformed hands, extra limbs, text, letters,
watermark, logo, misspelled words, speech bubble text, title text, subtitle text,
inconsistent haircut, fade haircut, tapered hair, slick hair, flat hair,
oversized cookies, oversized jar, mirrored room, random wardrobe change,
extra characters, NSFW, gore
""".strip()
