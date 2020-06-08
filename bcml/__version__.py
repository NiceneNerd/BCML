_major = 3
_minor = 0
_patch = "0b14"

VERSION = f"{_major}.{_minor}.{_patch}"
USER_VERSION = f"""{_major}.{_minor}.{_patch[0:1]} {
    'alpha' if _major < 1 else ''
}{
    f'beta {_patch[_patch.rindex("b") + 1:]}' if 'b' in _patch else ''
}"""
