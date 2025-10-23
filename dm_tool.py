#!/usr/bin/env python3
"""
main.py
- Loads bot tokens from tokens.txt
- Presents menu with options:
  1. DM Sender - Send DMs to opted-in users
  2. Fetch Users - Fetch all user IDs from a server and save to targets.txt
"""

import asyncio
import json
import logging
import os
import sys
from typing import List, Set

import discord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ANSI color codes
PURPLE = '\033[95m'
WHITE = '\033[97m'
RESET = '\033[0m'
BOLD = '\033[1m'

# ASCII Art Header
ASCII_HEADER = f"""{PURPLE}{BOLD}
 ▄▄▄▄    ██▓     ▒█████   ▒█████  ▓█████▄▓██   ██▓
▓█████▄ ▓██▒    ▒██▒  ██▒▒██▒  ██▒▒██▀ ██▌▒██  ██▒
▒██▒ ▄██▒██░    ▒██░  ██▒▒██░  ██▒░██   █▌ ▒██ ██░
▒██░█▀  ▒██░    ▒██   ██░▒██   ██░░▓█▄   ▌ ░ ▐██▓░
░▓█  ▀█▓░██████▒░ ████▓▒░░ ████▓▒░░▒████▓  ░ ██▒▓░
░▒▓███▀▒░ ▒░▓  ░░ ▒░▒░▒░ ░ ▒░▒░▒░  ▒▒▓  ▒   ██▒▒▒ 
▒░▒   ░ ░ ░ ▒  ░  ░ ▒ ▒░   ░ ▒ ▒░  ░ ▒  ▒ ▓██ ░▒░ 
 ░    ░   ░ ░   ░ ░ ░ ▒  ░ ░ ░ ▒   ░ ░  ░ ▒ ▒ ░░  
 ░          ░  ░    ░ ░      ░ ░     ░    ░ ░     
      ░                            ░      ░ ░     
 ██▒   █▓    ██▓                                  
▓██░   █▒   ▓██▒                                  
 ▓██  █▒░   ▒██▒                                  
  ▒██ █░░   ░██░                                  
   ▒▀█░     ░██░                                  
   ░ ▐░     ░▓                                    
   ░ ░░      ▒ ░                                  
     ░░      ▒ ░                                  
      ░      ░                                    
     ░                                            
{RESET}"""

def display_menu():
    """Display the main menu"""
    print(ASCII_HEADER)
    print(f"{WHITE}{'―' * 60}{RESET}")
    print(f"{WHITE}1. DM Sender - Send DMs to opted-in users{RESET}")
    print(f"{WHITE}2. Fetch Users - Fetch all user IDs from a server and save to targets.txt{RESET}")
    print(f"{WHITE}3. Exit{RESET}")
    print(f"{WHITE}{'―' * 60}{RESET}")

def load_tokens(path: str = "tokens.txt") -> List[str]:
    if not os.path.exists(path):
        print(f"{WHITE}tokens file not found: {path}{RESET}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except Exception as e:
        print(f"{WHITE}Error reading tokens file: {e}{RESET}")
        sys.exit(1)
        
    if not raw:
        print(f"{WHITE}tokens.txt is empty{RESET}")
        sys.exit(1)
    parts = []
    for part in raw.replace("\n", ",").split(","):
        t = part.strip()
        if t:
            parts.append(t)
    return parts

def load_targets(path: str = "targets.txt") -> List[int]:
    if not os.path.exists(path):
        print(f"{WHITE}targets file not found: {path}{RESET}")
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = [line.strip() for line in f.read().splitlines()]
    except Exception as e:
        print(f"{WHITE}Error reading targets file: {e}{RESET}")
        return []
        
    ids = []
    for l in raw_lines:
        if not l:
            continue
        if not l.isdigit():
            print(f"{WHITE}Skipping invalid ID: {l}{RESET}")
            continue
        ids.append(int(l))
    # de-duplicate while preserving order
    seen = set()
    uniq = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq

def save_targets(user_ids: Set[int], path: str = "targets.txt"):
    """Save user IDs to targets.txt, appending if file exists"""
    existing_ids = set()
    
    # Read existing IDs if file exists
    if os.path.exists(path):
        try:
            existing_targets = load_targets(path)
            existing_ids = set(existing_targets)
        except:
            existing_ids = set()
    
    # Combine existing and new IDs
    all_ids = existing_ids.union(user_ids)
    
    # Write all IDs to file
    try:
        with open(path, "w", encoding="utf-8") as f:
            for user_id in sorted(all_ids):
                f.write(f"{user_id}\n")
        
        new_count = len(user_ids - existing_ids)
        existing_count = len(existing_ids)
        total_count = len(all_ids)
        
        print(f"{WHITE}Saved {total_count} user IDs to {path}{RESET}")
        print(f"{WHITE} - {existing_count} existing IDs{RESET}")
        print(f"{WHITE} - {new_count} new IDs added{RESET}")
    except Exception as e:
        print(f"{WHITE}Error saving targets: {e}{RESET}")

async def fetch_users_from_guild(token: str, guild_id: int, result_queue: asyncio.Queue):
    """
    Connects a bot and fetches all user IDs from the specified guild.
    """
    intents = discord.Intents.all()  # Need all intents to fetch members
    client = discord.Client(intents=intents)

    token_preview = (token[:8] + "...") if token else "(empty)"
    result = {
        "token_preview": token_preview,
        "connected": False,
        "is_member": False,
        "user_ids": set(),
        "errors": [],
    }

    @client.event
    async def on_ready():
        try:
            result["connected"] = True
            me = client.user
            logging.info(f"[{token_preview}] Connected as {me} (id={me.id})")
            
            # Check guild membership and fetch members
            try:
                guild = await client.fetch_guild(guild_id)
                result["is_member"] = True
                logging.info(f"[{token_preview}] Bot is a member of guild {guild_id} (name: {getattr(guild, 'name', 'unknown')})")
                
                # Fetch all members from the guild
                logging.info(f"[{token_preview}] Fetching members from guild...")
                async for member in guild.fetch_members(limit=None):
                    if not member.bot:  # Exclude bots
                        result["user_ids"].add(member.id)
                
                logging.info(f"[{token_preview}] Fetched {len(result['user_ids'])} user IDs from guild")
                
            except discord.NotFound:
                result["is_member"] = False
                logging.warning(f"[{token_preview}] Bot is NOT a member of guild {guild_id}")
            except discord.Forbidden:
                result["errors"].append("Forbidden when fetching guild or members")
                logging.warning(f"[{token_preview}] Forbidden accessing guild {guild_id}")
            except Exception as e:
                result["errors"].append(f"Error fetching members: {e}")
                logging.exception(f"[{token_preview}] Error fetching members from guild {guild_id}: {e}")

            await client.close()
            await result_queue.put(result)
            
        except Exception as e:
            logging.exception(f"[{token_preview}] on_ready exception: {e}")
            result["errors"].append(f"on_ready exception: {e}")
            try:
                await client.close()
            except Exception:
                pass
            await result_queue.put(result)

    @client.event
    async def on_error(event, *args, **kwargs):
        logging.exception(f"[{token_preview}] Event {event} error")

    try:
        await client.start(token)
    except Exception as e:
        logging.exception(f"[{token_preview}] start/connection error: {e}")
        result["errors"].append(f"start error: {e}")
        await result_queue.put(result)

async def run_bot(token: str, guild_id: int, assigned_targets: List[int], message_text: str, result_queue: asyncio.Queue, per_message_delay: float = 1.5):
    """
    Connects a bot, checks membership, then DMs assigned targets if the bot is a member.
    Puts a result dictionary on result_queue when finished.
    """
    intents = discord.Intents.none()
    intents.guilds = True
    intents.members = True
    intents.presences = True
    client = discord.Client(intents=intents)

    token_preview = (token[:8] + "...") if token else "(empty)"
    result = {
        "token_preview": token_preview,
        "connected": False,
        "is_member": False,
        "members_intent_seems_on": False,
        "presence_intent_seems_on": False,
        "dm_sent": 0,
        "dm_failed": 0,
        "errors": [],
    }

    @client.event
    async def on_ready():
        try:
            result["connected"] = True
            me = client.user
            logging.info(f"[{token_preview}] Connected as {me} (id={me.id})")
            # Check guild membership
            try:
                guild = await client.fetch_guild(guild_id)
                result["is_member"] = True
                logging.info(f"[{token_preview}] Bot is a member of guild {guild_id} (name: {getattr(guild, 'name', 'unknown')})")
            except discord.NotFound:
                result["is_member"] = False
                logging.info(f"[{token_preview}] Bot is NOT a member of guild {guild_id}; skipping DMing.")
                await client.close()
                await result_queue.put(result)
                return
            except discord.Forbidden:
                result["errors"].append("Forbidden when fetching guild")
                logging.warning(f"[{token_preview}] Forbidden fetching guild {guild_id}")
                await client.close()
                await result_queue.put(result)
                return
            except Exception as e:
                result["errors"].append(f"fetch_guild error: {e}")
                logging.exception(f"[{token_preview}] Error fetching guild {guild_id}: {e}")
                await client.close()
                await result_queue.put(result)
                return

            # Heuristics for intents
            try:
                try:
                    cache_len = len(guild.members) if hasattr(guild, "members") else 0
                except Exception:
                    cache_len = 0
                if cache_len > 0:
                    result["members_intent_seems_on"] = True

                non_none_status = any(getattr(m, "status", None) is not None for m in getattr(guild, "members", []))
                if non_none_status:
                    result["presence_intent_seems_on"] = True
            except Exception:
                pass

            # Proceed to DM assigned targets
            if not assigned_targets:
                logging.info(f"[{token_preview}] No targets assigned to this bot. Closing.")
                await client.close()
                await result_queue.put(result)
                return

            logging.info(f"[{token_preview}] Sending DMs to {len(assigned_targets)} assigned target(s).")
            for target_id in assigned_targets:
                try:
                    user = await client.fetch_user(target_id)
                    if user is None:
                        logging.warning(f"[{token_preview}] Could not fetch user {target_id}")
                        result["dm_failed"] += 1
                        continue

                    try:
                        await user.send(message_text)
                        result["dm_sent"] += 1
                        logging.info(f"[{token_preview}] DM sent to {target_id}")
                    except discord.Forbidden:
                        logging.warning(f"[{token_preview}] Forbidden: cannot send DM to {target_id} (likely DMs closed).")
                        result["dm_failed"] += 1
                    except discord.HTTPException as he:
                        logging.warning(f"[{token_preview}] HTTPException when DMing {target_id}: {he}")
                        result["dm_failed"] += 1
                    except Exception as e:
                        logging.exception(f"[{token_preview}] Unexpected error sending DM to {target_id}: {e}")
                        result["dm_failed"] += 1

                    await asyncio.sleep(per_message_delay)
                except Exception as e:
                    logging.exception(f"[{token_preview}] Error processing target {target_id}: {e}")
                    result["dm_failed"] += 1

            logging.info(f"[{token_preview}] Finished sending DMs. Sent={result['dm_sent']}, Failed={result['dm_failed']}")
            await client.close()
            await result_queue.put(result)
        except Exception as e:
            logging.exception(f"[{token_preview}] on_ready exception: {e}")
            result["errors"].append(f"on_ready exception: {e}")
            try:
                await client.close()
            except Exception:
                pass
            await result_queue.put(result)

    @client.event
    async def on_error(event, *args, **kwargs):
        logging.exception(f"[{token_preview}] Event {event} error")

    try:
        await client.start(token)
    except Exception as e:
        logging.exception(f"[{token_preview}] start/connection error: {e}")
        result["errors"].append(f"start error: {e}")
        await result_queue.put(result)

def distribute_targets_among_tokens(targets: List[int], num_buckets: int) -> List[List[int]]:
    """
    Round-robin distribute targets into num_buckets so each bot gets a different set.
    """
    buckets = [[] for _ in range(num_buckets)]
    for i, t in enumerate(targets):
        buckets[i % num_buckets].append(t)
    return buckets

async def dm_sender_flow():
    """Handle the DM sender workflow"""
    print(f"{WHITE}=== DM Sender ==={RESET}")
    tokens = load_tokens("tokens.txt")
    print(f"{WHITE}Loaded {len(tokens)} token(s).{RESET}")
    
    guild_id_raw = input(f"{WHITE}Enter the server (guild) ID to check: {RESET}").strip()
    if not guild_id_raw.isdigit():
        print(f"{WHITE}Guild ID must be numeric.{RESET}")
        return
    guild_id = int(guild_id_raw)

    targets_path = input(f"{WHITE}Enter targets file path (default targets.txt): {RESET}").strip() or "targets.txt"
    targets = load_targets(targets_path)
    if not targets:
        print(f"{WHITE}No valid target IDs found in targets file.{RESET}")
        return
    print(f"{WHITE}Loaded {len(targets)} unique target user IDs from {targets_path}.{RESET}")

    message_text = input(f"{WHITE}Enter the message to DM the opted-in users (single line): {RESET}").strip()
    if not message_text:
        print(f"{WHITE}Empty message; aborting.{RESET}")
        return

    print(f"{WHITE}Process started. Bots will begin sending DMs to assigned targets (opt-ins).{RESET}")

    assignments = distribute_targets_among_tokens(targets, len(tokens))

    per_message_delay = 1.5
    result_queue = asyncio.Queue()
    tasks = []
    
    max_concurrent_connections = min(16, len(tokens))
    sem = asyncio.Semaphore(max_concurrent_connections)

    async def wrapper(tok, assigned):
        async with sem:
            await run_bot(tok, guild_id, assigned, message_text, result_queue, per_message_delay=per_message_delay)

    for tok, assigned in zip(tokens, assignments):
        tasks.append(asyncio.create_task(wrapper(tok, assigned)))

    results = []
    for _ in range(len(tasks)):
        res = await result_queue.get()
        results.append(res)
        tp = res["token_preview"]
        print(f"{WHITE}[{tp}] connected={res['connected']} is_member={res['is_member']} sent={res['dm_sent']} failed={res['dm_failed']} errors={len(res['errors'])}{RESET}")

    await asyncio.gather(*tasks, return_exceptions=True)

    with open("dm_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"{WHITE}Done. Report saved to dm_report.json{RESET}")

async def fetch_users_flow():
    """Handle the user fetching workflow"""
    print(f"{WHITE}=== User Fetcher ==={RESET}")
    tokens = load_tokens("tokens.txt")
    print(f"{WHITE}Loaded {len(tokens)} token(s).{RESET}")
    
    guild_id_raw = input(f"{WHITE}Enter the server (guild) ID to fetch users from: {RESET}").strip()
    if not guild_id_raw.isdigit():
        print(f"{WHITE}Guild ID must be numeric.{RESET}")
        return
    guild_id = int(guild_id_raw)

    print(f"{WHITE}Starting to fetch users from the server...{RESET}")
    print(f"{WHITE}All bots will go online and collect user IDs...{RESET}")

    result_queue = asyncio.Queue()
    tasks = []
    
    max_concurrent_connections = min(16, len(tokens))
    sem = asyncio.Semaphore(max_concurrent_connections)

    async def wrapper(token):
        async with sem:
            await fetch_users_from_guild(token, guild_id, result_queue)

    for token in tokens:
        tasks.append(asyncio.create_task(wrapper(token)))

    all_user_ids = set()
    results = []
    
    for _ in range(len(tasks)):
        res = await result_queue.get()
        results.append(res)
        all_user_ids.update(res["user_ids"])
        
        tp = res["token_preview"]
        print(f"{WHITE}[{tp}] connected={res['connected']} is_member={res['is_member']} users_fetched={len(res['user_ids'])} errors={len(res['errors'])}{RESET}")

    await asyncio.gather(*tasks, return_exceptions=True)

    if all_user_ids:
        save_targets(all_user_ids)
        print(f"{WHITE}\nSuccessfully collected {len(all_user_ids)} unique user IDs from guild {guild_id}{RESET}")
        print(f"{WHITE}User IDs have been saved/added to targets.txt{RESET}")
    else:
        print(f"{WHITE}\nNo user IDs were collected. Possible reasons:{RESET}")
        print(f"{WHITE}- Bots are not members of the specified guild{RESET}")
        print(f"{WHITE}- Guild doesn't exist or bots lack permissions{RESET}")
        print(f"{WHITE}- No users in the guild{RESET}")

    with open("fetch_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"{WHITE}Detailed report saved to fetch_report.json{RESET}")

async def main():
    try:
        while True:
            display_menu()
            choice = input(f"{WHITE}Select an option (1-3): {RESET}").strip()
            
            if choice == "1":
                await dm_sender_flow()
            elif choice == "2":
                await fetch_users_flow()
            elif choice == "3":
                print(f"{WHITE}Goodbye!{RESET}")
                break
            else:
                print(f"{WHITE}Invalid option. Please select 1, 2, or 3.{RESET}")
            
            input(f"{WHITE}\nPress Enter to continue...{RESET}")
    except KeyboardInterrupt:
        print(f"\n{WHITE}Interrupted by user. Goodbye!{RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{WHITE}Interrupted by user. Goodbye!{RESET}")
