from __future__ import annotations

from app.libs.example import greet


def test_greet() -> None:
    assert greet("World") == "Hello, World!"
