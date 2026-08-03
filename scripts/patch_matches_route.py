"""Patch match_type into _match_to_dict_full in matches.py route."""
path = "apps/api/routes/v1/matches.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = '        "status": m.status,\n        "home_score": m.home_score,'
new = '        "status": m.status,\n        "match_type": getattr(m, "match_type", "LEAGUE"),\n        "home_score": m.home_score,'

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK: match_type added to _match_to_dict_full")
else:
    # Try with CRLF
    old2 = '        "status": m.status,\r\n        "home_score": m.home_score,'
    new2 = '        "status": m.status,\r\n        "match_type": getattr(m, "match_type", "LEAGUE"),\r\n        "home_score": m.home_score,'
    if old2 in content:
        content = content.replace(old2, new2, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("OK: match_type added (CRLF variant)")
    else:
        print("WARN: Pattern not found")
        # Show context
        idx = content.find('"home_score": m.home_score')
        print(repr(content[max(0, idx-120):idx+60]))
