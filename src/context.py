"""
Store Context Configuration

Provides domain context to the LLM for better category pairing decisions.
Customize this for your specific store/industry.
"""

# =============================================================================
# STORE CONTEXT
# This is passed to the LLM to help it understand your business
# =============================================================================

STORE_CONTEXT = """
## Store Overview
WPSG (Western Public Safety Group) is a B2B supplier of safety equipment, tactical gear, 
and industrial supplies. Primary customers are:
- Fire departments and first responders
- Law enforcement agencies
- Military and tactical units
- Industrial safety professionals

## Product Categories (High Level)
- **Fire/Rescue Equipment**: Helmets, turnout gear, extrication tools, SCBA
- **Law Enforcement**: Duty gear, body armor, tactical equipment, firearms accessories
- **EMS/Medical**: Medical kits, bags, patient care supplies
- **Tactical Apparel**: Uniforms, boots, gloves, eyewear
- **Communications**: Radios, headsets, accessories
- **Lighting**: Flashlights, headlamps, area lights
- **Safety Equipment**: PPE, high-visibility, respiratory protection

## Cross-Sell Philosophy
We want to recommend items that:
1. Are REQUIRED accessories (radio needs a strap)
2. Are commonly used TOGETHER in the field (boots + boot socks)
3. COMPLETE an outfit or kit (tactical pants + tactical belt)
4. Are MAINTENANCE items (boot care for boots)

We do NOT want to recommend:
- Unrelated items from different job functions (fire helmet + gun holster)
- Items that serve the same purpose (two different flashlights)
- Consumables to durable goods without clear relationship
"""

# =============================================================================
# CATEGORY CONTEXT ENRICHMENT
# Add descriptions for your key child categories
# =============================================================================

CATEGORY_DESCRIPTIONS = {
    # Fire/Rescue
    "Fire Helmets": "Structural firefighting helmets, wildland helmets, rescue helmets",
    "Helmet Accessories": "Face shields, goggles, helmet lights, nomex covers, chin straps",
    "Turnout Gear": "Bunker coats, bunker pants, structural firefighting PPE",
    "Gloves - Fire": "Structural firefighting gloves, extrication gloves, wildland gloves",
    
    # Tactical/LE
    "Tactical Pants": "BDU pants, cargo pants, duty pants for law enforcement/military",
    "Tactical Belts": "Duty belts, rigger belts, inner/outer belt systems",
    "Tactical Boots": "Combat boots, duty boots, side-zip boots",
    "Body Armor": "Ballistic vests, plate carriers, soft armor panels",
    "Holsters": "Duty holsters, concealment holsters, light-bearing holsters",
    
    # Communications
    "Portable Radios": "Two-way radios, handheld transceivers",
    "Radio Accessories": "Radio straps, holders, speaker mics, earpieces",
    "Headsets": "Tactical headsets, hearing protection with comms",
    
    # Apparel Accessories
    "Boot Socks": "Tactical socks, moisture-wicking socks, duty socks",
    "Boot Care": "Polish, conditioner, waterproofing, replacement laces",
    "Gloves - Tactical": "Shooting gloves, patrol gloves, mechanic gloves",
    
    # Lighting
    "Flashlights": "Tactical flashlights, duty lights, weapon lights",
    "Headlamps": "Hands-free lighting, helmet-mounted lights",
    "Light Accessories": "Batteries, chargers, filters, holsters",
}

# =============================================================================
# PAIRING HINTS
# Known-good and known-bad pairings to help LLM calibrate
# =============================================================================

KNOWN_GOOD_PAIRINGS = [
    ("Tactical Pants", "Tactical Belts", "Complete uniform"),
    ("Tactical Boots", "Boot Socks", "Footwear essentials"),
    ("Portable Radios", "Radio Accessories", "Required accessories"),
    ("Fire Helmets", "Helmet Accessories", "Helmet customization"),
    ("Flashlights", "Light Accessories", "Batteries/holsters needed"),
    ("Body Armor", "Armor Plates", "Carrier needs plates"),
]

KNOWN_BAD_PAIRINGS = [
    ("Fire Helmets", "Holsters", "Different job functions"),
    ("Tactical Boots", "Fire Helmets", "Unrelated equipment"),
    ("Portable Radios", "Turnout Gear", "Different categories entirely"),
    ("Flashlights", "Tactical Pants", "No logical connection"),
]


def get_category_context(category_name: str) -> str:
    """Get description for a category if available."""
    return CATEGORY_DESCRIPTIONS.get(category_name, "")


def build_enriched_prompt(
    source_category: str,
    target_category: str,
    include_examples: bool = True,
) -> str:
    """
    Build a context-rich prompt for LLM validation.
    """
    source_desc = get_category_context(source_category)
    target_desc = get_category_context(target_category)
    
    context_section = f"""
## Category Details
- **{source_category}**: {source_desc if source_desc else 'No description available'}
- **{target_category}**: {target_desc if target_desc else 'No description available'}
"""
    
    examples_section = ""
    if include_examples:
        good_examples = "\n".join(
            f"  - {s} → {t}: ✅ {r}" for s, t, r in KNOWN_GOOD_PAIRINGS[:3]
        )
        bad_examples = "\n".join(
            f"  - {s} → {t}: ❌ {r}" for s, t, r in KNOWN_BAD_PAIRINGS[:3]
        )
        examples_section = f"""
## Calibration Examples
Good pairings:
{good_examples}

Bad pairings:
{bad_examples}
"""
    
    return f"""
{STORE_CONTEXT}
{context_section}
{examples_section}
"""
