"""Shared helper so every matplotlib chart carries a self-contained caption.

Each script's plot() calls add_caption() with a short paragraph that spells
out abbreviations and any detail needed to read the chart without the
surrounding script or README.
"""


def add_caption(fig, text, *, y=0.02):
    fig.text(0.02, y, text, ha="left", va="bottom", fontsize=8.5,
              color="#444", wrap=True)
