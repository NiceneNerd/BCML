extern crate pyo3;
extern crate indexmap;
extern crate lexical;
extern crate serde;
extern crate yaml_rust;

use pyo3::prelude::*;
use pyo3::types::*;
use indexmap::IndexMap;
use std::convert::From;
use std::str::FromStr;
use serde::{Deserialize, de};
use serde_yaml::Value;

#[derive(Debug,Deserialize)]
struct Vec2 {
    #[serde(deserialize_with="f32_from_str")]
    x: f32,
    #[serde(deserialize_with="f32_from_str")]
    y: f32
}

#[derive(Debug, Deserialize)]
struct Vec3 {
    #[serde(deserialize_with="f32_from_str")]
    x: f32,
    #[serde(deserialize_with="f32_from_str")]
    y: f32,
    #[serde(deserialize_with="f32_from_str")]
    z: f32
}

#[derive(Debug, Deserialize)]
struct Vec4 {
    #[serde(deserialize_with="f32_from_str")]
    x: f32,
    #[serde(deserialize_with="f32_from_str")]
    y: f32,
    #[serde(deserialize_with="f32_from_str")]
    z: f32,
    #[serde(deserialize_with="f32_from_str")]
    w: f32
}

#[derive(Debug, Deserialize)]
struct Color {
    r: f32,
    g: f32,
    b: f32,
    a: f32
}

#[derive(Debug, Deserialize)]
struct Quat {
    #[serde(deserialize_with="f32_from_str")]
    a: f32,
    #[serde(deserialize_with="f32_from_str")]
    b: f32,
    #[serde(deserialize_with="f32_from_str")]
    c: f32,
    #[serde(deserialize_with="f32_from_str")]
    d: f32
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum CurveVal {
    #[serde(deserialize_with="i32_from_str")]
    Int(i32),
    #[serde(deserialize_with="f32_from_str")]
    Float(f32)
}

impl ToPyObject for CurveVal {
    fn to_object(&self, py: Python) -> PyObject {
        match self {
            CurveVal::Float(f) => f.to_object(py),
            CurveVal::Int(i) => i.to_object(py),
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all="lowercase")]
enum Parameter {
    #[serde(deserialize_with="bool_from_str")]
    B(bool),
    N(CurveVal),
    #[serde(deserialize_with="u32_from_str")]
    U(u32),
    S(String),
    Vec2(Vec2),
    Vec3(Vec3),
    Vec4(Vec4),
    Curve(Vec<CurveVal>),
    Color(Color),
    Quat(Quat),
    Str32(String),
    Str64(String),
    Str256(String),
}


fn i32_from_str<'de, D>(deserializer: D) -> Result<i32, D::Error>
where
    D: de::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    let i = i32::from_str(s.as_str());
    match i {
        Result::Ok(i) => Ok(i),
        Result::Err(_) => Ok(0)
    }
}

fn u32_from_str<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: de::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    let u = u32::from_str(s.as_str());
    match u {
        Result::Ok(u) => Ok(u),
        Result::Err(_) => Ok(0)
    }
}

fn f32_from_str<'de, D>(deserializer: D) -> Result<f32, D::Error>
where
    D: de::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    let f = lexical::parse::<f32, _>(s.as_bytes());
    match f {
        Result::Ok(f) => Ok(f),
        Result::Err(_) => Ok(0.0)
    }
}

fn bool_from_str<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: de::Deserializer<'de>,
{
    let s = String::deserialize(deserializer).unwrap();
    Ok(s.as_str() == "true")
}

#[derive(Debug, Deserialize)]
struct ParameterList {
    lists: IndexMap<Value, ParameterList>,
    objects: IndexMap<Value, ParameterObject>
}

#[derive(Debug, Deserialize)]
struct ParameterObject(IndexMap<Value, Parameter>);

#[derive(Debug, Deserialize)]
pub struct ParameterIO {
    version: i32,
    #[serde(rename = "type")]
    data_type: String,
    param_root: ParameterList
}

impl IntoPyDict for ParameterIO {
    fn into_py_dict(self, py: Python) -> &PyDict {
        let dict = PyDict::new(py);
        dict.set_item("version", self.version).unwrap();
        dict.set_item("type", self.data_type).unwrap();
        let plists = PyDict::new(py);
        plists.set_item("param_root", self.param_root.into_py_dict(py)).unwrap();
        dict.set_item("lists", plists).unwrap();
        let pobjs = PyDict::new(py);
        dict.set_item("objects", pobjs).unwrap();
        &dict
    }
}

fn parse_key(key: Value) -> String {
    match key {
        Value::String(s) => s,
        Value::Number(n) => n.to_string(),
        _ => "".to_string()
    }
}

impl IntoPyDict for ParameterList {
    fn into_py_dict(self, py: Python) -> &PyDict {
        let dict = PyDict::new(py);
        let plists = PyDict::new(py);
        for (key, val) in self.lists.into_iter() {
            plists.set_item(parse_key(key), val.into_py_dict(py)).unwrap();
        }
        dict.set_item("lists", plists).unwrap();
        let pobjs = PyDict::new(py);
        for (key, val) in self.objects.into_iter() {
            pobjs.set_item(parse_key(key), val.into_py_dict(py)).unwrap();
        }
        dict.set_item("objects", pobjs).unwrap();
        &dict
    }
}

impl IntoPyDict for ParameterObject {
    fn into_py_dict(self, py: Python) -> &PyDict {
        let dict = PyDict::new(py);
        let params = PyDict::new(py);
        for (key, val) in self.0.into_iter() {
            let v: PyObject = val.into_py(py);
            params.set_item(parse_key(key), v).unwrap();
        }
        dict.set_item("params", params).unwrap();
        &dict
    }
}

impl IntoPy<PyObject> for Parameter {
    fn into_py(self, py: Python) -> PyObject {
        match self {
            Parameter::B(b) => b.to_object(py),
            Parameter::Color(c) => {
                let wrap_dict = PyDict::new(py);
                wrap_dict.set_item("_type", "Color").unwrap();
                let dict = PyDict::new(py);
                dict.set_item("r", c.r).unwrap();
                dict.set_item("g", c.g).unwrap();
                dict.set_item("b", c.b).unwrap();
                dict.set_item("a", c.a).unwrap();
                wrap_dict.set_item("value", dict).unwrap();
                PyObject::from(wrap_dict.as_ref())
            },
            Parameter::Curve(c) => {
                let dict = PyDict::new(py);
                dict.set_item("_type", "Curve").unwrap();
                let array = PyList::new(py, c.into_iter());
                dict.set_item("value", array).unwrap();
                PyObject::from(dict.as_ref())
            },
            Parameter::N(n) => {
                match n {
                    CurveVal::Float(f) => f.to_object(py),
                    CurveVal::Int(i) => i.to_object(py)
                }
            },
            Parameter::U(u) => u.to_object(py),
            Parameter::Quat(q) => {
                let wrap_dict = PyDict::new(py);
                wrap_dict.set_item("_type", "Quat").unwrap();
                let dict = PyDict::new(py);
                dict.set_item("a", q.a).unwrap();
                dict.set_item("b", q.b).unwrap();
                dict.set_item("c", q.c).unwrap();
                dict.set_item("d", q.d).unwrap();
                wrap_dict.set_item("value", dict).unwrap();
                PyObject::from(wrap_dict.as_ref())
            },
            Parameter::Vec2(v) => {
                let wrap_dict = PyDict::new(py);
                wrap_dict.set_item("_type", "Vec2").unwrap();
                let dict = PyDict::new(py);
                dict.set_item("x", v.x).unwrap();
                dict.set_item("y", v.y).unwrap();
                wrap_dict.set_item("value", dict).unwrap();
                PyObject::from(wrap_dict.as_ref())
            },
            Parameter::Vec3(v) => {
                let wrap_dict = PyDict::new(py);
                wrap_dict.set_item("_type", "Vec3").unwrap();
                let dict = PyDict::new(py);
                dict.set_item("x", v.x).unwrap();
                dict.set_item("y", v.y).unwrap();
                dict.set_item("z", v.z).unwrap();
                wrap_dict.set_item("value", dict).unwrap();
                PyObject::from(wrap_dict.as_ref())
            },
            Parameter::Vec4(v) => {
                let wrap_dict = PyDict::new(py);
                wrap_dict.set_item("_type", "Vec4").unwrap();
                let dict = PyDict::new(py);
                dict.set_item("x", v.x).unwrap();
                dict.set_item("y", v.y).unwrap();
                dict.set_item("z", v.z).unwrap();
                dict.set_item("z", v.w).unwrap();
                wrap_dict.set_item("value", dict).unwrap();
                PyObject::from(wrap_dict.as_ref())
            },
            Parameter::S(s) => s.to_object(py),
            Parameter::Str32(s) => {
                let dict = PyDict::new(py);
                dict.set_item("_type", "String32").unwrap();
                dict.set_item("value", s).unwrap();
                PyObject::from(dict.as_ref())
            },
            Parameter::Str64(s) => {
                let dict = PyDict::new(py);
                dict.set_item("_type", "String64").unwrap();
                dict.set_item("value", s).unwrap();
                PyObject::from(dict.as_ref())
            },
            Parameter::Str256(s) => {
                let dict = PyDict::new(py);
                dict.set_item("_type", "String256").unwrap();
                dict.set_item("value", s).unwrap();
                PyObject::from(dict.as_ref())
            }
        }
    }
}