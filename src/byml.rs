extern crate serde;
extern crate serde_json;
extern crate yaml_rust;

use std::collections::HashMap;
use serde::{Serialize, Deserialize};
use yaml_rust::Yaml;

#[derive(Serialize, Deserialize)]
#[serde(tag="_type", content="value")]
pub enum Number {
    Int(i32),
    UInt(u32),
    Float(f32)
}

#[derive(Serialize, Deserialize)]
#[serde(untagged)]
pub enum BymlNode {
    Null,
    Number(Number),
    String(String),
    Boolean(bool),
    List(Vec<BymlNode>),
    Dict(HashMap<String, BymlNode>)
}

fn parse_number(num: &Yaml) -> Option<Number> {
    match num {
        Yaml::Integer(i) => {
            if *i <= 2147483647 {
                Option::Some(Number::Int((*i as i32).into()))
            } else {
                Option::Some(Number::UInt((*i as u32).into()))
            }
        }
        Yaml::Real(r) => {
            Option::Some(Number::Float(r.parse::<f32>().unwrap()))
        }
        _ => Option::None
    }
}

pub fn parse_node(node: &Yaml) -> BymlNode {
    match node {
        Yaml::String(s) => { 
            let s2 = s.clone();
            if s.starts_with("0x") {
                let i = u32::from_str_radix(&s2.as_str()[2..], 16).unwrap();
                BymlNode::Number(
                    Number::UInt(i)
                )
            } else {
                BymlNode::String(s2)
            }
         }
        Yaml::Boolean(b) => { BymlNode::Boolean(*b) }
        Yaml::Array(a) => {
            BymlNode::List(
                a.iter().map(|n| parse_node(n)).collect::<Vec<BymlNode>>()
            )
        }
        Yaml::Hash(h) => {
            let mut data: HashMap<String, BymlNode> = HashMap::new();
            for entry in h.clone().entries() {
                data.insert(
                    String::from(entry.key().clone().into_string().unwrap()),
                    parse_node(entry.get())
                );
            }
            BymlNode::Dict(data)
        }
        Yaml::Integer(_) | Yaml::Real(_) => { BymlNode::Number(parse_number(&node).unwrap()) }
        _ => { BymlNode::Null }
    }
}