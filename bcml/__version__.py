_major = 3
_minor = 0
_patch = "0b2"
VERSION = f"{_major}.{_minor}.{_patch}"
USER_VERSION = f"""{_major}.{_minor}.{_patch[0:1]} {
    'alpha' if _major < 1 else ''
}{
    'beta' if 'b' in _patch else ''
}"""
