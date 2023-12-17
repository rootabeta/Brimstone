use anyhow::Error;
use core::sync::atomic::{AtomicBool, Ordering};
use color_eyre::eyre::Result;
use device_query::DeviceState;
use missilesystem::{create_session, wait_for_keypress, BanResult, ErrorState};
use prettyprinter::*;
use radar::*;
use rand::seq::SliceRandom;
use rand::thread_rng;
use std::collections::HashSet;
use std::fs;
use std::sync::Arc;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;
use toml::Table;
use ureq::Agent;

mod missilesystem;
mod prettyprinter;
mod radar;

/// Prints out the banner of the program by embedding the banner at compiletime
fn banner() {
    let contents = include_str!("banner.txt");
    println!("{}", contents);
}

/// Load the config, or percolate error upwards
fn load_config(config_file: &str) -> Result<Table, Error> {
    let config: Table = toml::from_str(config_file)?;
    Ok(config)
}

fn main() -> Result<()> {
    // Startup
    color_eyre::install()?;
    banner();

    // Load settings from config file
    let config_file = match fs::read_to_string("config.toml") {
        Ok(config_data) => config_data,
        Err(e) => panic!("Could not open config.toml!\n{e}"),
    };

    let config = match load_config(config_file.as_str()) {
        Ok(configuration) => configuration,
        Err(error) => panic!("Failed to interpret config.toml!\n{error}"),
    };

    // If loading a field fails, use a default value that's sensible for most anti-liberation work
    let Some(main_config) = config.get("config") else {
        panic!("Expected [config] block in config file!");
    };

    // Load WA-only setting, defaulting to True if corrupted or not found
    let wa_only: bool = match main_config.get("wa_only") {
        Some(boolean) => boolean.as_bool().unwrap_or(true),
        None => {
            warning("Could not find setting \"wa_only\" in config file! Assuming \"true\", but in the future, check that your config is valid.");
            true
        }
    };

    // Load whether or not to spare ROs, defaulting to sparing them if corrupted or not found
    let spare_ros: bool = match main_config.get("ignore_ros") {
        Some(boolean) => boolean.as_bool().unwrap_or(true),
        None => {
            warning("Could not find setting \"ignore_ros\" in config file! Assuming \"true\", but in the future, check that your config is valid.");
            true
        }
    };

    // Load whether or not to ban unknown nations, defaulting to yes
    let ban_bogeys: bool = match main_config.get("target_bogeys") {
        Some(boolean) => boolean.as_bool().unwrap_or(true),
        None => {
            warning("Could not find setting \"target_bogeys\" in config file! Assuming \"true\", but in the future, check that your config is valid.");
            true
        }
    };

    // Load whether to shut down Brimstone as soon as update occurs
    // Note, since we have fine-grained control over the ban process now, we can do this better
    // than in Python by aborting in-progress bans post-keypress, bc we can add a catch just before
    // the request to call it off if the cancel order has come in
    let upd_killswitch: bool = match main_config.get("stoponupdate") {
        Some(boolean) => boolean.as_bool().unwrap_or(true),
        None => {
            warning("Could not find setting \"stoponupdate\" in config file! Assuming \"true\", but in the future, check that your config is valid.");
            true
        }
    };

    // Load whether to ignore nations already in the region when Brimstone starts
    let ignore_residents: bool = match main_config.get("ignore_residents") {
        Some(boolean) => boolean.as_bool().unwrap_or(true),
        None => {
            warning("Could not find setting \"ignore_residents\" in config file! Assuming \"true\", but in the future, check that your config is valid.");
            true
        }
    };

    // Load desired delay per API request, with a minimum of 600ms permitted
    let delay: u64 = match main_config.get("pollspeed") {
        Some(integer) => {
            let value = integer.as_integer().unwrap_or(650);
            // API poll speeds faster than 1 request per 600ms would violate the API rate limit. So, if the speed specified is below that, use 600 instead.
            if value < 600 {
                warning("API poll speeds faster than 1 request every 600ms are against NationStates rules. Setting to 600ms between requests.");
                600
            } else {
                value.try_into().unwrap()
            }
        }
        None => {
            warning("Could not find setting \"pollspeed\" in config file! Assuming 650ms, but in the future, check that your config is valid.");
            650
        }
    };

    let jitter: i64 = match main_config.get("jitter") {
        Some(integer) => integer.as_integer().unwrap_or(0),
        None => {
            warning("Could not find setting \"jitter\" in config file! Assuming 0ms, but in the future, check that your config is valid.");
            0
        }
    };

    let region_override: &str = match main_config.get("region_override") {
        Some(option) => option.as_str().unwrap_or(""),
        None => {
            warning("Could not find setting \"region_override\" in config file! Assuming current region, but in the future, check that your config is valid.");
            ""
        }
    };

    let region_override = canonicalize(region_override);

    info("Successfully loaded configuration file");

    // Fetch user information - main nation, RO nation, and RO password
    let user = canonicalize(&ask("Main nation:"));
    // Identify yourself, or suffer my curse...
    if user.is_empty() {
        // Suffer the Pharaoh's curse (curse approved by the actual Pharaoh of Osiris)
        error("Main nation is a required parameter!");
        panic!("Suffer the Pharaoh's Curse");
    }

    let ro_nation = canonicalize(&ask("RO nation:"));
    let password = password("Password:");

    // Print out current settings
    println!();
    info("SETTINGS:");
    indent(format!("Main Nation:        {user}").as_str());
    indent(format!("RO Nation:          {ro_nation}").as_str());
    println!();
    indent(format!("Only target WA:     {wa_only}").as_str());
    indent(format!("Ignore ROs:         {spare_ros}").as_str());
    indent(format!("Ignore residents:   {ignore_residents}").as_str());
    indent(format!("Ban unknowns:       {ban_bogeys}").as_str());
    indent(format!("Killswitch:         {upd_killswitch}").as_str());
    println!();
    indent(format!("Delay interval:     {delay}ms").as_str());

    indent(format!("Jitter:             {jitter:0>3}ms").as_str());
    if !region_override.is_empty() {
        println!();
        warning("REGION OVERRIDE ENABLED");
        indent(format!("Override:           {region_override}").as_str());
    }
    println!();
    info("Initializing SAM site, please wait...");
    let user_agent_api = format!(
        "Brimstone/{} (API Component); Developed by nation=Volstrostia; In use by {}",
        env!("CARGO_PKG_VERSION"),
        canonicalize(&user),
    );

    let user_agent_html = format!(
        "Brimstone/{} (HTML Component); Developed by nation=Volstrostia; In use by {}",
        env!("CARGO_PKG_VERSION"),
        canonicalize(&user),
    );

    // Create API and Website clients (one for each end of the site)
    let api_client: Agent = ureq::AgentBuilder::new()
        .user_agent(user_agent_api.as_str())
        .timeout_read(Duration::from_secs(5))
        .timeout_write(Duration::from_secs(5))
        .build();

    let html_client: Agent = ureq::AgentBuilder::new()
        .user_agent(user_agent_html.as_str())
        .timeout_read(Duration::from_secs(5))
        .timeout_write(Duration::from_secs(5))
        .build();

    let device_state = DeviceState::new();

    let mut brimstone_session = create_session(&api_client, &ro_nation, &delay).expect(
        "Failed to create Brimstone session, possibly due to a typoed RO nation name\nGot error",
    );

    let current_region: &str;
    if !region_override.is_empty() {
        current_region = &region_override;
        brimstone_session.override_region(&current_region);
    } else {
        current_region = &brimstone_session.region;
    }

    // We could call login() here, if we wanted. But I don't want to break workflows.

    info("Initializing IFF system, please wait...");

    let mut iff: IFF = IFF {
        bogey_mode: match ban_bogeys {
            true => BogeyMode::BanUnknowns,
            false => BogeyMode::SpareUnknowns,
        },
        whitelist_explicit: HashSet::new(),
        whitelist_implicit: HashSet::new(),
        blacklist_explicit: HashSet::new(),
        blacklist_implicit: HashSet::new(),
    };

    let Some(whitelist_config) = config.get("whitelist") else {
        panic!("Expected [whitelist] block in config file!");
    };

    let Some(blacklist_config) = config.get("blacklist") else {
        panic!("Expected [blacklist] block in config file!");
    };

    if spare_ros {
        for nation in iff_get_officers(&api_client, &delay, &current_region)
            .expect(format!("Failed to access RO list for {current_region}").as_str())
        {
            let nation = canonicalize(&nation.to_string());
            iff.whitelist_explicit.insert(nation);
        }
    }

    if ignore_residents {
        info(&format!("Adding all nations in {current_region} to whitelist").to_string());
        for nation in iff_get_nations(
            &api_client,
            &delay,
            &canonicalize(&current_region.to_string()),
        )
        .expect(format!("Failed to access nationlist for {current_region}").as_str())
        {
            iff.whitelist_implicit.insert(canonicalize(&nation));
        }
    }

    if let Some(whitelisted_nations) = whitelist_config
        .get("nations")
        .expect("Expected nations block in whitelist")
        .as_array()
    {
        for nation in whitelisted_nations {
            let nation: String = canonicalize(&nation.as_str().unwrap());
            iff.whitelist_explicit.insert(nation);
        }
    }

    if let Some(blacklisted_nations) = blacklist_config
        .get("nations")
        .expect("Expected nations block in blacklist")
        .as_array()
    {
        for nation in blacklisted_nations {
            let nation: String = canonicalize(&nation.as_str().unwrap());
            iff.blacklist_explicit.insert(nation);
        }
    }

    // TODO: This probably needs better error-handling
    // For each region, fetch the list of nations
    if let Some(whitelisted_regions) = whitelist_config
        .get("regions")
        .expect("Expected regions block in whitelist")
        .as_array()
    {
        for region in whitelisted_regions {
            let region = region.as_str().expect("Broken region name");
            info(&format!("Adding all nations in {region} to whitelist").to_string());
            for nation in iff_get_nations(&api_client, &delay, &canonicalize(&region.to_string()))
                .expect(format!("Failed to access nationlist for {region}").as_str())
            {
                iff.whitelist_implicit.insert(canonicalize(&nation));
            }
        }
    }

    // Do the same for the blacklist regions
    if let Some(blacklisted_regions) = blacklist_config
        .get("regions")
        .expect("Expected regions block in blacklist")
        .as_array()
    {
        for region in blacklisted_regions {
            let region = region.as_str().expect("Broken region name");
            info(&format!("Adding all nations in {region} to blacklist").to_string());
            for nation in iff_get_nations(&api_client, &delay, &canonicalize(&region.to_string()))
                .expect(format!("Failed to access nationlist for {region}").as_str())
            {
                iff.blacklist_implicit.insert(canonicalize(&nation));
            }
        }
    }

    info("IFF System Initialized");
    indent(&format!("Explicitly permitted:  {}", iff.whitelist_explicit.len()).to_string());
    indent(&format!("Implicitly permitted:  {}", iff.whitelist_implicit.len()).to_string());
    indent(&format!("Explicitly targetted:  {}", iff.blacklist_explicit.len()).to_string());
    indent(&format!("Implicitly targetted:  {}", iff.blacklist_implicit.len()).to_string());

    ready(
        &format!("Ready to eliminate incursions into the airspace of {current_region}").to_string(),
    );
    let mut activation_confirm = ask("Activate SAM site? (Y/n)");
    activation_confirm.make_ascii_lowercase();
    if !activation_confirm.is_empty() && activation_confirm.starts_with("n") {
        info("Aborting SAM site startup at user request");
        return Ok(());
    }

    let current_region = String::from(current_region);

    let _ = match brimstone_session.login(&api_client, &ro_nation, &password, &delay) {
        Ok(_) => ready("SAM site initialized. Press SPACE to arm missiles."),
        Err(error) => panic!("Failed to log in to RO nation. Error: {error}"),
    };

    // This is where the fun begins
    let mut timestamp: u128;
    // Block until a keypress is detected
    timestamp = wait_for_keypress(&device_state);

    let _ = match brimstone_session.arm(&html_client, &timestamp) {
        Ok(_) => success("Missiles armed."),
        Err(error) => panic!("Failed to arm. Error: {error}"),
    };

    let (radartx, radarrx) = mpsc::channel();
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    let ctrlc = running.clone();

    ctrlc::set_handler(move || {
        info("Disarming missiles at user request.");
        ctrlc.store(false, Ordering::SeqCst);
    }).expect("Error setting Ctrl-C handler");

    let radar_handle = thread::spawn(move || {
        // Initialize
        let initialization;
        let mut old_nations;
        let mut nations;
        let last_update: u64;

        if wa_only {
            initialization = get_wa_nations(&api_client, &current_region)
                .expect("Radar failure during initialization");
        } else {
            initialization = get_nations(&api_client, &current_region)
                .expect("Radar failure during initialization");
        }

        old_nations = initialization.nations;
        last_update = initialization.last_update;

        // This will run forever until radar is terminated
        while r.load(Ordering::SeqCst) {
            let radar_ping;
            if wa_only {
                radar_ping = get_wa_nations(&api_client, &current_region).expect("Radar failure");
            } else {
                radar_ping = get_nations(&api_client, &current_region).expect("Radar failure");
            }

            // If we're watching for it to update, and it does, stop the presses
            if upd_killswitch && radar_ping.last_update > last_update {
                radartx.send(RadarCommand::HoldFire).unwrap();
                r.store(false, Ordering::SeqCst);
                break;
            }

            nations = radar_ping.nations;
            for nation in old_nations.iter() {
                // If there was a nation that isn't here anymore, quietly drop it off the radar -
                // maybe someone else got it. Let's focus on the ones that are in our face.
                if !nations.iter().any(|e| e.eq(nation)) {
                    radartx
                        .send(RadarCommand::Seperate(nation.to_string()))
                        .unwrap();
                }
            }

            for nation in nations.iter() {
                if !old_nations.iter().any(|e| e.eq(nation)) {
                    // IFF System
                    // Explicit whitelist
                    if iff.whitelist_explicit.contains(&canonicalize(&nation)) {
                        friendly_detected(&nation);
                    // Explicit blacklist
                    } else if iff.blacklist_explicit.contains(&canonicalize(&nation)) {
                        bandit_detected(&nation);
                        radartx
                            .send(RadarCommand::Inbound(nation.to_string()))
                            .unwrap();
                    // Implicit blacklist
                    } else if iff.blacklist_implicit.contains(&canonicalize(&nation)) {
                        bandit_detected(&nation);
                        radartx
                            .send(RadarCommand::Inbound(nation.to_string()))
                            .unwrap();
                    // Implicit whitelist
                    } else if iff.whitelist_implicit.contains(&canonicalize(&nation)) {
                        friendly_detected(&nation);
                    } else if iff.bogey_mode == BogeyMode::SpareUnknowns {
                        bogey_detected_safe(&nation);
                    } else {
                        bogey_detected_ban(&nation);
                        radartx
                            .send(RadarCommand::Inbound(nation.to_string()))
                            .unwrap();
                    }
                }
            }
            // Update our nation list from a second ago with the new details for the next go-around
            old_nations = nations;

            // Very last thing we do before another go-around is delay
            // Soooo remember that comment about how the API client in this doesn't self-rate-limit
            // and how I have to be very careful about doing it after finishing the data processing
            // and before sending another API request?
            thread::sleep(Duration::from_millis(delay));

            // Yeah guess what I forgot to do
            // I'm sorry [v] please don't DEAT me
        }

        /*
        // Simulated bogeys
        radartx.send(RadarCommand::Inbound(String::from("alex_fierro"))).unwrap();
        radartx.send(RadarCommand::Inbound(String::from("operation_mindcrime"))).unwrap();
        radartx.send(RadarCommand::Inbound(String::from("saul_rightdude"))).unwrap();

        // Simulated departure
        radartx.send(RadarCommand::Seperate(String::from("operation_mindcrime"))).unwrap();

        // If we don't care about going past update, then simply... don't bother telling anyone
        // when it updates
        if upd_killswitch {
            radartx.send(RadarCommand::HoldFire(())).unwrap();
        }
        */
    });

    success("Radar online.");

    // RNG driver
    let mut rng = thread_rng();

    // Start the radar
    // The radar will be a thread that constantly polls the API and can send one of three signals.
    // ADD(), the most common, informs the controller of a new nation. REMOVE() does the opposite,
    // and instructs the controller to remove a given nation if present. Finally, SHUTDOWN(),
    // which is communicated over a SEPERATE PIPE, indicates that the region has updated (and that
    // we care about that, given the configuration) and that futher ban attempts should be abandoned
    // to allow the program to gracefully exit.
    // These events are sent down two channels to the main thread for processing.

    // Start the primary control loop
    // The control loop does a few things every time it goes around.
    let mut splash_count = 0;

    // Bank of stuff we don't want to target
    let mut skippable = HashSet::new();
    // Bank of stuff we *do* want to target
    let mut bogeys = Vec::new();
    'control_loop: while running.load(Ordering::SeqCst) {
        // 1) It checks if there are any new items waiting for it in the channel. If so, it steps
        //    through the various commands as they come in - this should be in order of appearance,
        //    conveniently. If, at any point, it encounters an ABORT, it will break immediately.
        loop {
            let _ = match radarrx.try_recv() {
                Ok(radar_data) => match radar_data {
                    RadarCommand::Inbound(nation) => bogeys.push(nation),
                    RadarCommand::Seperate(nation) => {
                        bogeys.retain(|x| !x.eq(&nation));
                    }
                    RadarCommand::HoldFire => {
                        info("HOLD FIRE; TARGET HAS UPDATED");
                        break 'control_loop;
                    }
                },
                Err(_) => {
                    break;
                }
            };
        }

        // If there is at least one target available to us,
        if !bogeys.is_empty() {
            // 2) Once it has processed the remaining events, it is confident that its internal memory is
            //    the freshest available representation of the region state. It also knows that every
            //    target it has in its memory is a potentially valid target - i.e., not forbidden by IFF.
            //    It will then attempt to select a target at random, and compare it to an internal
            //    hashset of all skipped or banned targets. If it is not in the hashset, then we know this
            //    target has not been declared unbannable yet, and has not been banned, AND that it is a
            //    valid target for elimination. However, if it is found in the hashset, it is dropped from the vector,
            //    and the code that performs the waiting for a keypress is skipped entirely, allowing the control loop
            //    to return to the top - specifically, to re-do step 1. This means that each time we check for potential
            //    targets, we are using the freshest data available at that moment. This means the main thread effectively
            //    spins, continually refreshing its target cache, until a valid target is found. When one is eventually found,
            //    the if condition that gates the ban is armed, allowing phase 3 to begin.

            // Select a random target
            let target: &str = bogeys.choose(&mut rng).unwrap();
            let target = String::from(target);

            // If we drew a target we need to skip, draw a new one without attempting to yeet - we
            // know the attempt will fail, so why bother? Easier and faster than trying to prune
            // the list.
            if skippable.contains(&target) {
                continue;
            }

            missile_lock(&target);

            // 3) Once a valid target has been selected, Brimstone locks itself behind a keybind, and waits
            //    for a keypress to come in. When this keypress comes in, Brimstone knows that we are
            //    authorized to ban the selected target, and will immediately dispatch a function call to
            //    ban that nation. However, before it does this, it checks to make sure that no abort order
            //    has come in since the last time we checked - if not, it launches the request immediately,
            //    but if so, then it refuses to initiate the request and instead breaks out of the control
            //    loop with an explanation.
            timestamp = wait_for_keypress(&device_state);

            // If the region updated *while* waiting on the keypress, now we can catch that by
            // checking if running is still set to true - it will be falsified if we need to abort.
            if !running.load(Ordering::SeqCst) {
                break 'control_loop;
            }

            let _ = match brimstone_session.yeet(&html_client, &target, &timestamp) {
                Ok(banresult) => match banresult {
                    // Successfully banned the target - don't bother banning it again
                    BanResult::Success => {
                        hit_confirmed(&target);
                        skippable.insert(target);
                        splash_count += 1;
                    }

                    // Failed to ban the target for some reason, but the request didn't explode
                    BanResult::Failure(failure) => {
                        let _ = match failure.try_again_later() {
                            // E.g. not enough influence. Don't bother taking aim at this one.
                            ErrorState::Skip => {
                                fail_hit_skip(&target);
                                skippable.insert(target);
                            }
                            // E.g. lost BCRO during delbump. Nothing we can do anymore - shut down
                            ErrorState::Abort => {
                                fail_hit_skip(&target);
                                error("FATAL ERROR EXPERIENCED; BRIMSTONE CAN NO LONGER FUNCTION.");
                                indent("This is likely NOT a problem with Brimstone; you may have been logged out, lost BCRO, etc.");
                                indent("Nevertheless, Brimstone cannot continue under these circumstances and will now shut down immediately.");
                                break 'control_loop;
                            }
                            // E.g. ban cooldown was still in effect. Try again later.
                            ErrorState::TryAgain => {
                                fail_hit(&target);
                            }
                        };
                    }
                },

                // Request exploded :c
                Err(_) => match error {
                    _ => error("Got unresolved error during HTML request. Attempting to continue."),
                },
            };
        };
    }

    let splashed = format!("Hostiles splashed: {splash_count}");
    info(&splashed);

    // Shut down radar at the end of the program, for tidiness
    running.store(false, Ordering::SeqCst);
    radar_handle.join().unwrap();

    Ok(())
}
