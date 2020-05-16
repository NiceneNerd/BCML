import copyreg
from typing import Union
import oead


def pickle_pio(pio: oead.aamp.ParameterIO):
    return oead.aamp.ParameterIO.from_binary, (bytes(pio.to_binary()),)


def construct_plist(data: bytes) -> oead.aamp.ParameterList:
    return oead.aamp.ParameterIO.from_binary(data).lists["main"]


def pickle_plist(plist: oead.aamp.ParameterList):
    tmp_pio = oead.aamp.ParameterIO()
    tmp_pio.lists["main"] = plist
    return construct_plist, (bytes(tmp_pio.to_binary()),)


def construct_byml(data: bytes) -> Union[oead.byml.Hash, oead.byml.Array]:
    return oead.byml.from_binary(data)


def pickle_byml(byml: Union[oead.byml.Hash, oead.byml.Array]):
    return construct_byml, (bytes(oead.byml.to_binary(byml, big_endian=False)),)


def pickle_u32(u32: oead.U32):
    return oead.U32, (int(u32),)


pickle_map = {
    oead.aamp.ParameterIO: pickle_pio,
    oead.aamp.ParameterList: pickle_plist,
    oead.byml.Hash: pickle_byml,
    oead.byml.Array: pickle_byml,
    oead.U32: pickle_u32,
}

for typ, func in pickle_map.items():
    copyreg.pickle(typ, func)
