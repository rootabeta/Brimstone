use colored::Colorize;
use inquire::{Password, PasswordDisplayMode, Select, Text};

/// Used for general status updates
pub fn info(string: &str) {
    println!("\r[{}] {}", "INF".bold().cyan(), string);
}

/// Something went wrong, but not fatally
pub fn warning(string: &str) {
    println!("\r[{}] {}", "WRN".bold().yellow(), string);
}

/// Something went very, very wrong indeed
pub fn error(string: &str) {
    println!("\r[{}] {}", "ERR".bold().red(), string);
}

/// Something went great!
pub fn success(string: &str) {
    println!("\r[{}] {}", "SCS".bold().green(), string);
}

/// Something is ready for use - see success()
pub fn ready(string: &str) {
    println!("\r[{}] {}", "RDY".bold().green(), string);
}

/** Indent a string to the amount other prompts are.
 * Used to print out data on a new line without
 * preample or fanfare. Usually when you have
 * some long string of data to convey, without
 * providing the illusion of breaking it up into
 * a series of discrete messages.
*/
pub fn indent(string: &str) {
    println!("      {}", string);
}

/// We've detected an inbound, unidentified nation - and we want to kill it
pub fn bogey_detected_ban(nation: &str) {
    println!(
        "\r[{}] DETECTED INBOUND BOGEY: {} ; LAUNCH {}",
        "BGY".bold().yellow(),
        nation.to_uppercase().as_str(),
        "AUTHORIZED".bold()
    );
}

/// We've detected an inbound, unidentified nation - and we wish to spare it
pub fn bogey_detected_safe(nation: &str) {
    println!(
        "\r[{}] DETECTED INBOUND BOGEY: {} ; LAUNCH {} AUTHORIZED",
        "BGY".bold().yellow(),
        nation.to_uppercase().as_str(),
        "NOT".bold()
    );
}

/// We've detected a known-hostile nation
pub fn bandit_detected(nation: &str) {
    println!(
        "\r[{}] DETECTED HOSTILE BANDIT: {}",
        "BND".bold().red(),
        nation.to_uppercase().as_str()
    );
}

/// We've detected a known-friendly or whitelisted nation
pub fn friendly_detected(nation: &str) {
    println!(
        "\r[{}] DETECTED INBOUND FRIENDLY: {}",
        "FRN".bold().green(),
        nation.to_uppercase().as_str()
    );
}

/// It's up to you, captain - say the word, and they're falling shrapnel
pub fn missile_lock(nation: &str) {
    println!(
        "\r[{}] ACQUIRED MISSILE LOCK ON -=[ {} ]=- ; PRESS SPACE TO AUTHORIZE LAUNCH",
        "LCK".bold().red(),
        nation.to_uppercase().as_str()
    );
}

/// We knocked someone clean out of the sky and into TRR
pub fn hit_confirmed(nation: &str) {
    println!(
        "\r[{}] BIRD AWAY; CONFIRMED HIT; {} DOWNED",
        "HIT".bold().green(),
        nation.to_uppercase().as_str()
    );
}

/// We failed to launch a missile, for some mysterious reason
pub fn fail_hit(nation: &str) {
    println!(
        "\r[{}] BIRD NEGATIVE; COULD NOT ENGAGE {}; ACQUIRING NEW TARGET",
        "LOS".bold().red(),
        nation.to_uppercase().as_str()
    );
}

/// We failed to launch a missile, for some mysterious reason, AND we shouldn't try again
pub fn fail_hit_skip(nation: &str) {
    println!(
        "\r[{}] BIRD NEGATIVE; COULD NOT ENGAGE {}; TARGET NOT VALID FOR ENGAGEMENT",
        "LOS".bold().red(),
        nation.to_uppercase().as_str()
    );
}
/// Ask the user for a string - namely, their nation name
pub fn ask(string: &str) -> String {
    let response = Text::new(string).prompt();
    return response.unwrap();
}

/// Ask the user for their password, using ********s
pub fn password(string: &str) -> String {
    let response = Password::new(string)
        .with_display_mode(PasswordDisplayMode::Masked)
        .without_confirmation()
        .with_formatter(&|s| "*".repeat(s.len()))
        .prompt();
    return response.unwrap();
}

/// Ask the user to answer a yes or no question
pub fn yes_no(string: &str) -> bool { 
    let options: Vec<&str> = vec!["Yes", "No"];
    let response = Select::new(string, options).prompt().unwrap();
    if response == "Yes" { 
        true
    } else { 
        false
    }
}
