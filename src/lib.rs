#![feature(specialization)]
extern crate pyo3;
extern crate regex;
extern crate serde_json;
extern crate serde_yaml;
extern crate yaml_rust;

// use std::fs;
use regex::Regex;
use pyo3::prelude::*;
use pyo3::types::IntoPyDict;
use pyo3::exceptions;
use yaml_rust::{YamlLoader};
mod byml;
mod aamp;

#[pymodule]
fn lib_bcml(_py: Python, m: &PyModule) -> PyResult<()> {

    #[pyfn(m, "byml_yaml_to_json")]
    fn byml_yaml_to_json(yml: String) -> PyResult<String> {
        let doc = &YamlLoader::load_from_str(yml.as_str()).unwrap()[0];
        let data: byml::BymlNode = byml::parse_node(doc);
        match serde_json::to_string(&data) {
            Ok(s) => Result::Ok(s),
            Err(e) => return Err(exceptions::ValueError::py_err(e.to_string()))
        }
    }

    #[pyfn(m, "aamp_yaml_to_json")]
    fn aamp_yaml_to_json(_py: Python, yml: String) -> PyResult<PyObject> {
        let (head, body) = yml.split_at(24);
        let fixed = body
            .replace("!!float", "!n")
            .replace("!str32 \n", "!str32 \"\"\n")
            .replace("!str64 \n", "!str64 \"\"\n")
            .replace("!str256 \n", "!str256 \"\"\n")
            .replace(": false", ": !b false")
            .replace(": true", ": !b true");
        let re = Regex::new(r": ([\-0-9]+\.?[0-9]+)([\n ,\}])").unwrap();
        let fixed = re.replace_all(&fixed, ": !n $1$2");
        let re = Regex::new(r"(?s)!(\w+) (\[.+?\])").unwrap();
        let fixed = re.replace_all(&fixed, " { $1: $2 }");
        let re = Regex::new(r#": ([\w'"])"#).unwrap();
        let fixed = re.replace_all(&fixed, ": !s $1");
        let mut final_str = String::from(head);
        final_str.push_str(&fixed);
        PyResult::Ok(
            serde_yaml::from_str::<aamp::ParameterIO>(
                final_str.as_str()
            ).unwrap().into_py_dict(_py).into()
        )
    }
    Ok(())
}
