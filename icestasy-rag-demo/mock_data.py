FLAVOURS = [
    {"id": 1, "name": "Ratnagiri Hapoos Mango", "abbr": "RAT"},
    {"id": 2, "name": "Amrood Guava/Peru",      "abbr": "AMR"},
    {"id": 3, "name": "Palapazham Jackfruit",   "abbr": "PAL"},
    {"id": 4, "name": "Karikku Tender Coconut", "abbr": "KAR"},
    {"id": 5, "name": "Ukadiche Modak",         "abbr": "UKA"},
    {"id": 6, "name": "Chikkamagaluru Kaaphi",  "abbr": "CHI"},
    {"id": 7, "name": "Mysore Paak",            "abbr": "MYS"},
    {"id": 8, "name": "Belgian Speculoos",      "abbr": "BEL"},
]

PACK_FORMATS = [
    {"id": 1, "name": "4L Bulk",     "suffix": "4L",   "is_sample": False,
     "description": "One 4-litre tub. No minimum order."},
    {"id": 2, "name": "12 Square",   "suffix": "12SQ", "is_sample": False,
     "description": "12 individual pieces per unit."},
    {"id": 3, "name": "50ml Sample", "suffix": "50ML", "is_sample": True,
     "description": "Single-serve 50ml cups. Client visits only."},
]

SKUS = []
for f in FLAVOURS:
    for p in PACK_FORMATS:
        sku_code = f"{f['abbr']}-{p['suffix']}-{f['id']}"
        SKUS.append({
            "sku_code": sku_code,
            "flavour_id": f["id"],
            "flavour_name": f["name"],
            "flavour_abbr": f["abbr"],
            "pack_format_id": p["id"],
            "pack_format_name": p["name"],
            "pack_format_suffix": p["suffix"],
            "is_sample": p["is_sample"],
        })

INVENTORY = {
    "RAT-4L-1": 18,  "AMR-4L-2": 6,   "PAL-4L-3": 24,
    "KAR-4L-4": 11,  "UKA-4L-5": 0,   "CHI-4L-6": 33,
    "MYS-4L-7": 8,   "BEL-4L-8": 14,
    "RAT-12SQ-1": 45, "AMR-12SQ-2": 12, "PAL-12SQ-3": 7,
    "KAR-12SQ-4": 30, "UKA-12SQ-5": 2,  "CHI-12SQ-6": 19,
    "MYS-12SQ-7": 25, "BEL-12SQ-8": 9,
}
# 50ml samples
for f in FLAVOURS:
    INVENTORY[f"{f['abbr']}-50ML-{f['id']}"] = 200

KNOWLEDGE_BASE = [
    {
        "id": "flavour_rat",
        "text": "Ratnagiri Hapoos Mango — SKU prefix RAT. Premium Alphonso mango sourced from Ratnagiri. Available in 4L Bulk and 12 Square.",
        "tags": ["mango", "hapoos", "alphonso", "ratnagiri", "rat"],
    },
    {
        "id": "flavour_amr",
        "text": "Amrood Guava/Peru — SKU prefix AMR. Tropical guava flavour. Available in 4L Bulk and 12 Square.",
        "tags": ["guava", "amrood", "peru", "amr"],
    },
    {
        "id": "flavour_pal",
        "text": "Palapazham Jackfruit — SKU prefix PAL. South Indian jackfruit flavour. Available in 4L Bulk and 12 Square.",
        "tags": ["jackfruit", "palapazham", "pal"],
    },
    {
        "id": "flavour_kar",
        "text": "Karikku Tender Coconut — SKU prefix KAR. Fresh tender coconut flavour. Available in 4L Bulk and 12 Square.",
        "tags": ["coconut", "tender coconut", "karikku", "kar"],
    },
    {
        "id": "flavour_uka",
        "text": "Ukadiche Modak — SKU prefix UKA. Inspired by the Ganesh festival sweet. Available in 4L Bulk and 12 Square.",
        "tags": ["modak", "ukadiche", "ganesh", "uka"],
    },
    {
        "id": "flavour_chi",
        "text": "Chikkamagaluru Kaaphi — SKU prefix CHI. Coffee ice cream inspired by Chikkamagaluru estate coffee. Available in 4L Bulk and 12 Square.",
        "tags": ["coffee", "kaaphi", "kaapi", "chikkamagaluru", "chi"],
    },
    {
        "id": "flavour_mys",
        "text": "Mysore Paak — SKU prefix MYS. Classic Mysore ghee sweet as ice cream. Available in 4L Bulk and 12 Square.",
        "tags": ["mysore paak", "mysore pak", "ghee", "mys"],
    },
    {
        "id": "flavour_bel",
        "text": "Belgian Speculoos — SKU prefix BEL. Spiced biscuit flavour. Available in 4L Bulk and 12 Square.",
        "tags": ["speculoos", "biscuit", "belgian", "bel"],
    },
    {
        "id": "format_4l",
        "text": "4L Bulk — one unit is one 4-litre tub of ice cream. No minimum order quantity, a rep can order even a single unit. SKU suffix 4L. Suited for HoReCa, restaurants, catering, and large orders.",
        "tags": ["4l", "bulk", "tub", "horeca", "restaurant", "catering"],
    },
    {
        "id": "format_12sq",
        "text": "12 Square — one unit is exactly 12 individual ice cream pieces. Minimum order is 1 unit (12 pieces). SKU suffix 12SQ. Suited for retail counters, gifting, and events.",
        "tags": ["12sq", "12 square", "square", "retail", "gifting", "event"],
    },
    {
        "id": "format_sample",
        "text": "50ml Samples — single-serve 50ml cups. Used only for client visits and client meets. Not available for resale or standard orders. Reps can request samples when visiting a prospective client.",
        "tags": ["sample", "50ml", "client visit", "meet", "demo"],
    },
    {
        "id": "rule_minorder",
        "text": "4L Bulk has no minimum order. One unit = one 4-litre tub. Order as few as 1 unit. 12 Square minimum is 1 unit = exactly 12 pieces. Samples have no minimum and are only for client meetings.",
        "tags": ["minimum", "order", "quantity", "moq"],
    },
    {
        "id": "rule_samples",
        "text": "Samples (50ml) should only be requested when a rep is visiting a client or conducting a client meet. They are not a product for sale and cannot be added to a regular order.",
        "tags": ["sample", "client", "visit", "meet", "rule"],
    },
    {
        "id": "rule_oos",
        "text": "If a flavour is out of stock in the requested format, suggest the same flavour in the other format, or the nearest available flavour in the same format.",
        "tags": ["out of stock", "oos", "alternative", "substitute"],
    },
    {
        "id": "rule_delivery",
        "text": "Delivery: Mumbai next day. Pune 2 days. Other cities 3-5 days.",
        "tags": ["delivery", "shipping", "mumbai", "pune", "days"],
    },
]
