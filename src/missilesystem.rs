use anyhow::Error;
use device_query::{DeviceQuery, DeviceState, Keycode};
use select::document::Document;
use select::predicate::{Attr, Class};
use serde::Deserialize;
use serde_xml_rs::from_str;
use std::thread::sleep;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use ureq::Agent;

// Duplicate, because we use it here too apparently
fn canonicalize(string: &str) -> String {
    let mut output = String::from(string);
    output.make_ascii_lowercase();
    return str::replace(output.as_str(), " ", "_");
}

// TODO: Allow custom keycode
pub fn wait_for_keypress(device_state: &DeviceState) -> u128 {
    let mut keys: Vec<Keycode>;

    // Wait for space to appear in the list of pressed keys
    // i.e., wait for space to be pressed down
    loop {
        keys = device_state.get_keys();
        if keys.contains(&Keycode::Space) {
            break;
        }
    }

    // Now that we've seen space go *down*, wait for it to come back *up*
    loop {
        keys = device_state.get_keys();
        if !keys.contains(&Keycode::Space) {
            break;
        }
    }

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis();

    return timestamp;
}

/// Convenient bucket to store cookies and security check values
pub struct Session {
    chk: String, // Security check value - refreshed after every attempted ban, successful or not
    pin: String, // Session cookie - set on successful login over API
    pub region: String, // Region we are yeeting people from - set on first successful login
}

/// These are different ways we can fail to banject a nation
pub enum BanFailure {
    /// Region updated; stop the bans.
    //    StopOrdered,
    /// Not enough influence to ban
    NoInfluence,
    /// Already on ban list
    AlreadyBanned,
    /// We banned someone else too recently
    TooFast,
    /// We don't have BCRO
    NotAllowed,
    /// We aren't logged in
    //    NotAuthenticated,
    /// Some other, unknown reason
    Unknown,
}

pub enum BanResult {
    Success,
    Failure(BanFailure),
}

/// Different ways we can respond to failing to ban a nation
#[derive(Eq, PartialEq)]
pub enum ErrorState {
    /// Trying to ban this nation in the future might be successful
    TryAgain,
    /// Trying to ban this nation will always fail, so don't bother
    Skip,
    /// We shouldn't be trying to ban anything at all - stop asking.
    Abort,
}

impl BanFailure {
    /// Quickly check if a given failure type means we should try this target again later. If true,
    /// we can try again later and might succeed, but if false, we know any subsequent attempt will
    /// fail, so we can avoid trying to ban, for example, nations we have insufficient influence
    /// for. Showstopper errors, such as losing BCRO in a deltip, or getting the order to shut down
    /// Brimstone, not only tell the caller function to skip *this* target, but to abandon future
    /// ban attempts altogether.
    pub fn try_again_later(&self) -> ErrorState {
        let result = match &self {
            BanFailure::TooFast => ErrorState::TryAgain,
            BanFailure::Unknown => ErrorState::TryAgain,
            BanFailure::AlreadyBanned => ErrorState::Skip,
            BanFailure::NoInfluence => ErrorState::Skip,
            //            BanFailure::StopOrdered => ErrorState::Abort,
            BanFailure::NotAllowed => ErrorState::Abort,
            //            BanFailure::NotAuthenticated => ErrorState::Abort,
        };

        result
    }
}

#[derive(Deserialize)]
struct FetchRegion {
    #[serde(alias = "REGION")]
    region: String,
}

/// Create a template session we can log in with later and do banning things
/// Returns the current region as a cheeky little bonus
pub fn create_session(api_client: &Agent, nation: &str, delay: &u64) -> Result<Session, Error> {
    let chk = String::default(); // This gets filled in by the HTML side
    let pin = String::default(); // This gets filled in during login

    let url = format!("https://www.nationstates.net/cgi-bin/api.cgi?q=region&nation={nation}");
    let region = api_client
        .get(&url)
        .call()?
        .into_string()
        .expect("Failed to fetch region!");

    let region: FetchRegion = from_str(&region).unwrap();
    let region = String::from(canonicalize(&region.region));

    // Create a mutable session (so we can update the pin and chk values)
    let session = Session { pin, region, chk };

    sleep(Duration::from_millis(*delay));
    Ok(session)
}

impl Session {
    /// Convince Brimstone that it's actually operating in a different region than the nation it's
    /// using lives in
    pub fn override_region(&mut self, region: &str) {
        self.region = region.to_string();
    }

    /// Log in with the given username and password, returning an error on failure and setting
    /// self.pin and returning a valid session on success.
    /// We actually use the API client for this one, because this is an API request to log in and
    /// fetch the resulting value from the X-Pin header. We then take this value and feed it into
    /// the pin cookie for HTML requests, but this request is an API one - so we use the API agent.
    /// We also return the region we're in, as well as setting that internally for future reference
    /// Thank fuck that \[v\] herself confirmed that I can mix and match logins across API and HTML
    pub fn login(
        &mut self,
        api_client: &Agent,
        nation: &str,
        password: &str,
        delay: &u64,
    ) -> Result<(), Error> {
        // Perform login
        let url = format!("https://www.nationstates.net/cgi-bin/api.cgi?q=ping&nation={nation}");
        let pin = api_client
            .get(&url)
            .set("X-Password", password)
            .call()?
            .header("X-Pin")
            .expect("Login failed!")
            .trim()
            .to_string();

        sleep(Duration::from_millis(*delay));

        self.pin = pin;

        Ok(())
    }

    /// Fetch an initial chk value to prepare for the first yeet. Either we succeed, or we invoke
    /// an error - usually due to a failed or unattempted login. This and [yeet] are gated behind a
    /// userclick, even though this function technically is not restricted, to avoid issues with
    /// ratelimiting.
    pub fn arm(&mut self, html_client: &Agent, userclick: &u128) -> Result<(), Error> {
        if *userclick == 0 {
            panic!("Bogus userclick detected! Aborting execution! Please stop using this program and file a bug report!");
        }
        let url = format!("https://www.nationstates.net/page=region_control/region={}/template-overall=none/userclick={}", 
                          self.region,
                          userclick
                  );
        let cookie = format!("pin={}", self.pin);
        // ureq is a *blocking* HTML client, so it enforces simultaneity automatically so long as
        // there are not two threads using html_client at once, which there are not.

        let response = html_client
            .get(&url)
            .set("Cookie", &cookie)
            .call()?
            .into_string()?;

        // This code will look very familiar - we will do this to refresh the chk afterwards
        /*
        let soup = Soup::new(&response);
        let chk_input = soup
            .tag("input")
            .attr("name", "chk")
            .find()
            .expect("Couldn't extract chk");

        let chk = chk_input
            .get("value")
            .expect("Failed to extract chk from element");
        */

        let document = Document::from(response.as_str());
        for node in document.find(Attr("name", "chk")) {
            self.chk = node
                .attr("value")
                .expect("Couldn't extract chk")
                .to_string();
            break;
        }

        Ok(())
    }

    /**
     * Banject the target nation, and update the chk value with the result. The temptation to call
     * this function "yeet" is immense. Returns an empty value on success, because all we care
     * about is that it worked, or raises an error of some kind if we failed, which we can catch
     * to determine what happened - e.g. not enough influence, already banned (recoverable) or
     * bogus chk or pin (oh no)
     *
     * We can return our own errors containing, for example, Err(BanFailure::TooFast), to inform
     * the calling process that we could not ban for some reason - in this case, we've gone beyond
     * the 1s cooldown and the request was refused. This allows the calling process to be selective
     * about how to respond to failures to ban - for example, if it's because we don't have the
     * influence, we shouldn't try that target again later, but if it's because we were too fast, we
     * can try again some other time. This allows for smarter targetting than just treating all
     * failures equally.
     *
     * Edit: I gave into temptation
     */
    pub fn yeet(
        &mut self,
        html_client: &Agent,
        nation: &str,
        userclick: &u128,
    ) -> Result<BanResult, Error> {
        if *userclick == 0 {
            panic!("Bogus userclick detected! Aborting execution! Please stop using this program and file a bug report!");
        }

        let url = format!("https://www.nationstates.net/page=region_control/region={}/template-overall=none/userclick={}", 
                &self.region,
                userclick
              );

        let cookie = format!("pin={}", self.pin);
        // ureq is a *blocking* HTML client, so it enforces simultaneity automatically so long as
        // there are not two threads using html_client at once, which there are not.

        // Make a POST request this time
        let response = html_client
            .post(&url)
            .set("Cookie", &cookie)
            .send_form(&[("ban", "1"), ("nation_name", &nation), ("chk", &self.chk)])?
            .into_string()?;

        let document = Document::from(response.as_str());
        for node in document.find(Attr("name", "chk")) {
            self.chk = node
                .attr("value")
                .expect("Couldn't extract chk")
                .to_string();
            break;
        }

        // document.getElementsByClassName("error")[0].textContent; -> error of some kind
        // "You don't have enough regional influence to banject" -> influence

        // If we have an info class, then we know we've reached success
        if document.find(Class("info")).next().is_some() {
            Ok(BanResult::Success)
        } else {
            if let Some(error_message) = document.find(Class("error")).next() {
                let error_message = error_message.text();
                // 1s cooldown not yet expired
                if error_message.contains("heavy nation-shifting assets are currently deployed") {
                    Ok(BanResult::Failure(BanFailure::TooFast))
                // Not enough influence
                } else if error_message.contains("don't have enough regional influence") {
                    Ok(BanResult::Failure(BanFailure::NoInfluence))
                // Already banned
                } else if error_message.contains("is already on the")
                    && error_message.contains("ban list.")
                {
                    Ok(BanResult::Failure(BanFailure::AlreadyBanned))
                // Lost BCRO
                } else if error_message
                    .contains("You are not authorized to handle matters relating to Border Control")
                {
                    Ok(BanResult::Failure(BanFailure::NotAllowed))
                } else {
                    // Hopefully, this should never happen
                    println!("GOT UNPROCESSED BAN ERROR\n {error_message}");
                    Ok(BanResult::Failure(BanFailure::Unknown))
                }
            } else {
                Ok(BanResult::Failure(BanFailure::Unknown))
            }
        }
    }
}
