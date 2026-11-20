"""Smoke test - build the window, exercise every filter path, tear down."""

import sys

sys.path.insert(0, r"C:\Work\projects\rackjacked")

import catalog

assert len(catalog.TOOLS) > 0, "empty catalog"

names = [t["n"] for t in catalog.TOOLS]
assert len(names) == len(set(names)), "duplicate tool names: %s" % (
    sorted({n for n in names if names.count(n) > 1}),)

for t in catalog.TOOLS:
    for k in ("n", "c", "f", "d"):
        assert k in t and t[k], "missing %s in %r" % (k, t)
    assert t["c"] in catalog.CATEGORIES, "bad category %r" % t["c"]
    for L in t["f"]:
        assert L in "GSFIPRDCOMLW", "bad flag %r in %s" % (L, t["n"])
    if t.get("u"):
        assert t["u"].startswith("http"), "bad url %r" % t["u"]

import rackjacked as rj

app = rj.RackJacked()
app.update_idletasks()
app.update()

total = len(app.tree.get_children())
assert total == len(catalog.TOOLS), "tree rows %d != %d" % (total, len(catalog.TOOLS))

# category filter
app.active_cat = "Web"
app.refresh()
app.update_idletasks()
web = len(app.tree.get_children())
assert web == sum(1 for t in catalog.TOOLS if t["c"] == "Web"), "web filter broke"

# flag filter
app.active_cat = "ALL"
app.active_flags = {"G", "C"}
app.refresh()
app.update_idletasks()
gc = len(app.tree.get_children())
assert gc == sum(1 for t in catalog.TOOLS if "G" in t["f"] and "C" in t["f"]), "flag filter broke"

# search
app.active_flags.clear()
app.search_var.set("sqlmap")
app.refresh()
app.update_idletasks()
assert len(app.tree.get_children()) >= 1, "search broke"

# select + detail render
first = app.tree.get_children()[0]
app.tree.selection_set(first)
app.update()
body = app.d_text.get("1.0", "end")
assert app.d_head.cget("text") not in ("", "select a tool"), "detail head not filled"
assert len(body.strip()) > 40, "detail body empty"

app._clear_all()
app.update_idletasks()
assert len(app.tree.get_children()) == len(catalog.TOOLS), "reset broke"

# sorting both directions
app._sort("TOOL")
app.update_idletasks()
a = app.tree.item(app.tree.get_children()[0])["values"][0]
app._sort("TOOL")
app.update_idletasks()
b = app.tree.item(app.tree.get_children()[0])["values"][0]
assert a != b, "sort direction did not flip"

app.destroy()
print("SMOKE OK | tools=%d | web=%d | G+C=%d | detail=%d chars"
      % (len(catalog.TOOLS), web, gc, len(body)))
