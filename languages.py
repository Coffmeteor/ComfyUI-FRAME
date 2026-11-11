"""Exported labels are recipe-bound so remote clients do not need translation support."""
from __future__ import annotations

LANGUAGES = ("en", "zh", "bilingual")


def caption(english: str, chinese: str, language: str) -> str:
    if language not in LANGUAGES:
        raise ValueError("Choose English, Chinese or bilingual workflow labels")
    return chinese if language == "zh" else f"{english} / {chinese}" if language == "bilingual" else english


def recipe_language(recipe: dict) -> str:
    # Existing immutable recipes have Chinese field names. Never reinterpret them.
    return recipe.get("language", "zh")


QUALITY = (
    ("Landscape", "横图"), ("Square", "方图"), ("Phone wallpaper", "手机壁纸"),
    ("1 MP", "一百万像素"), ("SD redraw", "高清重绘"), ("Face detail", "面部细修"),
    ("SeedVR2 restoration", "SeedVR2修复"), ("Fixed image seed", "固定随机种子"),
    ("Alternate model", "备用模型"),
)
