from dataclasses import asdict, dataclass, field, is_dataclass
import json
from typing import Union

from aamp import parameters
import aamp.aamp as aamp
from aamp.yaml_util import _get_pstruct_name
import byml.byml as byml

class DummyReader:
    _crc32_to_string_map: dict = {}
DUMMY = DummyReader()
_try_name = lambda idx, k, parent_crc32: _get_pstruct_name(DUMMY, idx, k, parent_crc32)

class AampJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, aamp.ParameterIO):
            return self.encode_pio(o)
        elif isinstance(o, aamp.ParameterList):
            return self.encode_plist(o)
        elif isinstance(o, aamp.ParameterObject):
            return self.encode_pobject(o)
        else:
            return super().default(o)

    def encode_pio(self, pio: aamp.ParameterIO) -> dict:
        return {
            'type': pio.type,
            'version': pio.version,
            'lists': {_try_name(idx, k, pio._crc32): self.encode_plist(pl) for idx, (k, pl) in enumerate(pio.lists.items())},
            'objects': {_try_name(idx, k, pio._crc32): self.encode_pobject(pobj) for idx, (k, pobj) in enumerate(pio.objects.items())},
        }

    def encode_plist(self, plist: aamp.ParameterList) -> dict:
        return {
            'lists': {_try_name(idx, k, plist._crc32): self.encode_plist(pl) for idx, (k, pl) in enumerate(plist.lists.items())},
            'objects': {_try_name(idx, k, plist._crc32): self.encode_pobject(pobj) for idx, (k, pobj) in enumerate(plist.objects.items())},
        }

    def encode_pobject(self, obj: aamp.ParameterObject) -> dict:
        return {
            'params': {_try_name(idx, k, obj._crc32): self.encode_param(param) for idx, (k, param) in enumerate(obj.params.items())}
        }

    def encode_param(self, param) -> dict:
        type_name = type(param).__name__
        if getattr(parameters, type_name, None) is None:
            return param
        return {
            '_type': type(param).__name__,
            'value': asdict(param) if is_dataclass(param) else param
        }


def aamp_to_json(data: Union[bytes, aamp.Reader, dict], pretty: bool = False) -> str:
    if isinstance(data, bytes):
        data = aamp.Reader(data)
    if isinstance(data, aamp.Reader):
        data = data.parse()
    return json.dumps(data, cls=AampJSONEncoder, ensure_ascii=False, indent=4 if pretty else None)


class AampJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, o):
        try:
            iter(o)
        except:
            return o
        obj_type = type(o).__name__
        if getattr(parameters, obj_type, None) is not None:
            return o
        if getattr(aamp, obj_type, None) is not None:
            return o
        if 'version' in o:
            return self._to_pio(o)
        else:
            return o

    def _to_pobj(self, o) -> aamp.ParameterObject:
        if isinstance(o, aamp.ParameterObject):
            return o
        pobj = aamp.ParameterObject()
        if o['params']:
            for param, val in o['params'].items():
                if param.isnumeric():
                    pobj.params[int(param)] = self._to_param(val)
                else:
                    pobj.set_param(param, self._to_param(val))
        return pobj

    def _to_plist(self, o) -> aamp.ParameterList:
        plist = aamp.ParameterList()
        if isinstance(o, aamp.ParameterList):
            return o
        if o['lists']:
            for name, content in o['lists'].items():
                if name.isnumeric():
                    plist.lists[int(name)] = self._to_plist(content)
                else:
                    plist.set_list(name, self._to_plist(content))
        if o['objects']:
            for name, content in o['objects'].items():
                if content['params']:
                    if name.isnumeric():
                        plist.objects[int(name)] = self._to_pobj(content)
                    else:
                        plist.set_object(name, self._to_pobj(content))
        return plist

    def _to_pio(self, o) -> aamp.ParameterIO:
        pio = aamp.ParameterIO(o['type'], o['version'])
        if o['lists']:
            for name, content in o['lists'].items():
                if name.isnumeric():
                    pio.lists[int(name)] = self._to_plist(content)
                else:
                    pio.set_list(name, self._to_plist(content))
        if o['objects']:
            for name, content in o['objects'].items():
                if content['params']:
                    if name.isnumeric():
                        pio.objects[int(name)] = self._to_pobj(content)
                    else:
                        pio.set_object(name, self._to_pobj(content))
        return pio
    
    def _to_param(self, o):
        try:
            iter(o)
            param_type = getattr(parameters, o['_type'])
        except TypeError:
            return o
        if is_dataclass(param_type):
            return param_type(**o['value'])
        else:
            return param_type(o['value'])


def json_to_aamp(data: Union[str, bytes]) -> dict:
    if isinstance(data, bytes):
        data = data.decode(encoding='utf-8')
    json_data = json.loads(data, encoding='utf-8')
    dec = AampJSONDecoder()
    return {
        file: dec._to_plist(json_data[file]) for file in json_data
    }


class BymlJSONEncoder(json.JSONEncoder):
    """
    This class encodes BYML content to JSON format by subclassing `json.JSONEncoder`.
    However, because the `default()` method is by default only called for objects that
    the standard JSON encoder doesn't know how to handle, it will not work directly as
    plugged in as the `cls` argument for `json.dumps`. Instead, you can either call
    `BymlJsonEncoder.default()` directly before dumping, or you can use use the
    `byml_to_json()` utility function.
    """
    def default(self, o):
        if type(o) in {byml.Int, byml.Float, byml.UInt, byml.UInt64, byml.Int64, byml.Double}:
            return {
                '_type': type(o).__name__,
                'value': str(o)
            }
        elif isinstance(o, list):
            return [self.default(i) for i in o]
        elif isinstance(o, dict):
            return {k: self.default(v) for k, v in o.items()}
        try:
            return super(BymlJSONEncoder, self).default(o)
        except TypeError:
            return o


def byml_to_json(data: Union[bytes, byml.Byml, dict], pretty: bool = False) -> str:
    if isinstance(data, bytes):
        data = byml.Byml(data)
    if isinstance(data, byml.Byml):
        data = data.parse()
    json_obj = BymlJSONEncoder().default(data)
    return json.dumps(json_obj, ensure_ascii=False, indent=4 if pretty else None)


class BymlJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, o):
        try:
            obj_type = o['_type']
            return getattr(byml, obj_type)(o['value'])
        except KeyError:
            return o


def json_to_byml(data: Union[str, bytes]) -> dict:
    if isinstance(data, bytes):
        data = data.decode(encoding='utf-8')
    return json.loads(data, encoding='utf-8', cls=BymlJSONDecoder)