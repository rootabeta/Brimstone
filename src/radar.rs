use anyhow::Error;
use serde::Deserialize;
use serde_xml_rs::from_str;
use std::collections::HashSet;
use std::{thread, time};
use ureq::Agent;

pub struct IFF {
    pub bogey_mode: BogeyMode,
    pub whitelist_explicit: HashSet<String>,
    pub whitelist_implicit: HashSet<String>,
    pub blacklist_explicit: HashSet<String>,
    pub blacklist_implicit: HashSet<String>,
}

/// Used to handle responses from the API and turn them into useable values
#[derive(Deserialize)]
struct APIResponse {
    #[serde(alias = "NATIONS", alias = "UNNATIONS")]
    nations: String,
    #[serde(alias = "LASTUPDATE")]
    last_update: u64,
}

impl APIResponse {
    pub fn split_nations(&self) -> Vec<String> {
        let mut nations = Vec::new();
        // WANations and regular nations are formatted differently, because [v] hates me.
        if self.nations.contains(':') {
            for nation in self.nations.split(':') {
                nations.push(canonicalize(nation));
            }
        } else if self.nations.contains(',') {
            for nation in self.nations.split(',') {
                nations.push(canonicalize(nation));
            }
        }
        nations
    }
}

/// Option to either ban or not ban unrecognized nations.
/// Hey, is this doc a BogeyMan? Like, Bogey Manual? Boogeyman? Get it?
#[derive(Eq, PartialEq)]
pub enum BogeyMode {
    BanUnknowns,
    SpareUnknowns,
}

/// Convert a nation name from My Nation to my_nation
pub fn canonicalize(string: &str) -> String {
    let mut output = String::from(string);
    output.make_ascii_lowercase();
    return str::replace(output.as_str(), " ", "_");
}

/// Simple nationlist fetcher, used to populate IFF system
pub fn iff_get_nations(agent: &Agent, delay: &u64, region: &str) -> Result<Vec<String>, Error> {
    let mut nations = Vec::new();
    let url = format!(
        "https://www.nationstates.net/cgi-bin/api.cgi?q=nations+lastupdate&region={region}"
    );
    let response = agent.get(&url).call()?.into_string()?;
    let response: APIResponse = from_str(&response)?;
    for nation in response.split_nations() {
        nations.push(nation);
    }
    thread::sleep(time::Duration::from_millis(*delay));
    Ok(nations)
}

/// Each individual office
#[derive(Deserialize)]
struct Office {
    #[serde(alias = "NATION")]
    nation: String,
}

/// Each person, who can hold one or more offices
#[derive(Deserialize)]
struct Officer {
    #[serde(alias = "OFFICER")]
    officer: Vec<Office>,
}

/// Delegate and officers, from NS server
#[derive(Deserialize)]
struct ROs {
    #[serde(alias = "DELEGATE")]
    delegate: String,
    #[serde(alias = "OFFICERS")]
    officers: Vec<Officer>,
}

/// Get the ROs of a region, used to populate IFF system
pub fn iff_get_officers(agent: &Agent, delay: &u64, region: &str) -> Result<Vec<String>, Error> {
    let mut officers = Vec::new();

    let url =
        format!("https://www.nationstates.net/cgi-bin/api.cgi?q=officers+delegate&region={region}");
    let response = agent.get(&url).call()?.into_string()?;
    let response: ROs = from_str(&response)?;

    officers.push(canonicalize(&response.delegate));

    for officer in response.officers {
        for office in officer.officer {
            // This is so stupid...
            officers.push(canonicalize(&office.nation));
        }
    }

    thread::sleep(time::Duration::from_millis(*delay));
    Ok(officers)
}

/// Signals that the radar can send to the missile system
pub enum RadarCommand {
    // New nation inbound
    Inbound(String),
    // Previously tracked nation outbound
    Seperate(String),
    // Shut down the SAM site
    HoldFire,
}

pub struct RadarReading {
    pub nations: Vec<String>,
    pub last_update: u64,
}

/// Get a list of all nations in a region and return the vector immediately
/// PITFALL: MAKE SURE YOU DO THE DELAY AFTER CALLING THIS. The delay is not done in-function
/// so as to give the calling function the results ASAP. These should only ever be called with a
/// delay gated after their data is consumed prior to another request.
pub fn get_nations(agent: &Agent, region: &str) -> Result<RadarReading, Error> {
    let mut nations = Vec::new();
    let url = format!(
        "https://www.nationstates.net/cgi-bin/api.cgi?q=nations+lastupdate&region={region}"
    );
    let response = agent.get(&url).call()?.into_string()?;
    let response: APIResponse = from_str(&response)?;
    for nation in response.split_nations() {
        nations.push(nation);
    }

    let reading = RadarReading {
        nations,
        last_update: response.last_update,
    };

    Ok(reading)
}

/// Get a list of all WA nations in a region and return the result immediately.
/// See notes for get_nations on preventing a developer pitfall related to rate limits.
pub fn get_wa_nations(agent: &Agent, region: &str) -> Result<RadarReading, Error> {
    let mut nations = Vec::new();
    let url = format!(
        "https://www.nationstates.net/cgi-bin/api.cgi?q=wanations+lastupdate&region={region}"
    );
    let response = agent.get(&url).call()?.into_string()?;
    let response: APIResponse = from_str(&response)?;
    for nation in response.split_nations() {
        nations.push(nation);
    }

    let reading = RadarReading {
        nations,
        last_update: response.last_update,
    };

    Ok(reading)
}
