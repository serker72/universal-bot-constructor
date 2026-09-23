"""Тесты санитизации HTML описания объекта (bot.html_sanitize)."""

import pytest

from app.bot.html_sanitize import sanitize_html


def test_allowed_tags_kept():
    assert sanitize_html("<b>Жирный</b> и <i>курсив</i>") == "<b>Жирный</b> и <i>курсив</i>"


def test_nested_allowed_tags():
    html = "<b>Пиццерия <i>Bella Napoli</i></b>"
    assert sanitize_html(html) == html


def test_disallowed_tags_stripped_content_kept():
    assert sanitize_html("<div>Текст</div>") == "Текст"


def test_dangerous_content_dropped():
    assert sanitize_html("a<script>alert(1)</script>b") == "ab"
    assert sanitize_html("a<style>p{}</style>b") == "ab"


def test_text_escaped():
    # символы вне тегов экранируются
    assert sanitize_html("5 < 6 & 7 > 3") == "5 &lt; 6 &amp; 7 &gt; 3"


def test_link_href_kept_other_attrs_dropped():
    out = sanitize_html('<a href="https://example.com" onclick="x()">Сайт</a>')
    assert out == '<a href="https://example.com">Сайт</a>'


def test_link_href_escaped():
    out = sanitize_html('<a href="https://ex.com/?a=1&b=<x>">l</a>')
    assert out == '<a href="https://ex.com/?a=1&amp;b=&lt;x&gt;">l</a>'


def test_br_converted():
    assert sanitize_html("строка<br/>вторая") == "строка<br>вторая"


def test_empty_input():
    assert sanitize_html("") == ""
    assert not sanitize_html("")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('🍕 <b>Название</b><i>Описание</i>', '🍕 <b>Название</b><i>Описание</i>'),
        ("<code class=\"language-python\">x=1</code>", '<code class="language-python">x=1</code>'),
        # ammonia рендерит булев атрибут как expandable="" — Telegram принимает
        ("<blockquote expandable>…</blockquote>", '<blockquote expandable="">…</blockquote>'),
    ],
)
def test_examples(raw: str, expected: str):
    assert sanitize_html(raw) == expected


def test_escape_text_removed():
    # текст вне тегов экранируется средствами nh3
    assert sanitize_html("5 < 6 & 7 > 3") == "5 &lt; 6 &amp; 7 &gt; 3"
