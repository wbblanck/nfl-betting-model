from nflbet.ui import fx


def test_animations_only_inside_reduced_motion_guard():
    css = fx.css()
    guard = css.index("@media (prefers-reduced-motion:no-preference)")
    assert "animation:" not in css[:guard] and "transition:" not in css[:guard]
    assert "animation:" in css[guard:]


def test_every_tab_has_an_icon():
    css = fx.css()
    for tab in ("s1", "ats", "mix", "engine", "outliers", "trends"):
        assert f'data-tab="{tab}"' in css
    assert "%ICONS%" not in css
