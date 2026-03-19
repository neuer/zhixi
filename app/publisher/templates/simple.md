# {{ title }}

> {{ summary }}

---

{% for item in items %}
## {{ item.display_order }}. {{ item.snapshot_title }}

{{ item.snapshot_translation }}

**点评**: {{ item.snapshot_comment }}

{% endfor %}

---

*智曦 — 每天一束AI之光*
