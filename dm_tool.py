#!/usr/bin/env python3
"""
main.py
- Enter tokens directly in the tool
- Bots go online, then enter server ID and message
- DMs all users in the server automatically with no duplicates
"""

import asyncio
import json
import logging
import sys
from typing import List, Set, Dict
from collections import defaultdict

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
    print(f"{WHITE}1. Start DM Tool - Enter tokens and send DMs{RESET}")
    print(f"{WHITE}2. Exit{RESET}")
    print(f"{WHITE}{'―' * 60}{RESET}")

def get_tokens_from_input():
    """Get bot tokens from user input"""
    print(f"\n{WHITE}=== Enter Bot Tokens ==={RESET}")
    print(f"{WHITE}Enter bot tokens (comma separated):{RESET}")
    print(f"{WHITE}Example: token1,token2,token3{RESET}")
    tokens_input = input(f"{WHITE}Tokens: {RESET}").strip()
    
    if not tokens_input:
        print(f"{WHITE}No tokens entered!{RESET}")
        return []
    
    # Split by comma and clean up
    tokens = []
    for token in tokens_input.split(','):
        cleaned_token = token.strip()
        if cleaned_token:
            tokens.append(cleaned_token)
    
    print(f"{WHITE}Loaded {len(tokens)} token(s){RESET}")
    return tokens

async def fetch_all_users_from_guild(token: str, guild_id: int, result_queue: asyncio.Queue):
    """
    Connects a bot and fetches all users from the specified guild.
    """
    intents = discord.Intents.all()
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
                logging.info(f"[{token_preview}] Bot is a member of guild {guild_id}")
                
                # Fetch all members from the guild
                logging.info(f"[{token_preview}] Fetching members from guild...")
                async for member in guild.fetch_members(limit=None):
                    if not member.bot:  # Exclude bots
                        result["user_ids"].add(member.id)
                
                logging.info(f"[{token_preview}] Fetched {len(result['user_ids'])} users from guild")
                
            except discord.NotFound:
                result["is_member"] = False
                logging.warning(f"[{token_preview}] Bot is NOT a member of guild {guild_id}")
            except discord.Forbidden:
                result["errors"].append("Forbidden when fetching guild or members")
                logging.warning(f"[{token_preview}] Forbidden accessing guild {guild_id}")
            except Exception as e:
                result["errors"].append(f"Error: {e}")
                logging.exception(f"[{token_preview}] Error processing guild {guild_id}: {e}")

            await client.close()
            await result_queue.put(result)
            
        except Exception as e:
            logging.exception(f"[{token_preview}] on_ready exception: {e}")
            result["errors"].append(f"on_ready exception: {e}")
            try:
                await client.close()
            except:
                pass
            await result_queue.put(result)

    try:
        await client.start(token)
    except Exception as e:
        logging.exception(f"[{token_preview}] start/connection error: {e}")
        result["errors"].append(f"start error: {e}")
        try:
            await client.close()
        except:
            pass
        await result_queue.put(result)

async def dm_assigned_users(token: str, assigned_users: List[int], message_text: str, result_queue: asyncio.Queue, per_message_delay: float = 2.0):
    """
    Connects a bot and DMs only the assigned users.
    """
    intents = discord.Intents.none()
    intents.guilds = True
    client = discord.Client(intents=intents)

    token_preview = (token[:8] + "...") if token else "(empty)"
    result = {
        "token_preview": token_preview,
        "connected": False,
        "dm_sent": 0,
        "dm_failed": 0,
        "errors": [],
        "assigned_count": len(assigned_users)
    }

    @client.event
    async def on_ready():
        try:
            result["connected"] = True
            me = client.user
            logging.info(f"[{token_preview}] Connected as {me} (id={me.id})")
            
            # DM each assigned user
            if assigned_users:
                logging.info(f"[{token_preview}] Starting to DM {len(assigned_users)} assigned users...")
                for i, user_id in enumerate(assigned_users):
                    try:
                        # Fetch user and send DM
                        user = await client.fetch_user(user_id)
                        await user.send(message_text)
                        result["dm_sent"] += 1
                        logging.info(f"[{token_preview}] DM sent to {user_id} - {i+1}/{len(assigned_users)}")
                        
                    except discord.Forbidden:
                        logging.warning(f"[{token_preview}] Cannot DM {user_id} (DMs closed)")
                        result["dm_failed"] += 1
                    except discord.HTTPException as he:
                        logging.warning(f"[{token_preview}] HTTP error DMing {user_id}: {he}")
                        result["dm_failed"] += 1
                    except Exception as e:
                        logging.exception(f"[{token_preview}] Error DMing {user_id}: {e}")
                        result["dm_failed"] += 1

                    # Rate limiting delay
                    await asyncio.sleep(per_message_delay)
                
                logging.info(f"[{token_preview}] Finished DMs. Sent: {result['dm_sent']}, Failed: {result['dm_failed']}")
            else:
                logging.info(f"[{token_preview}] No users assigned to this bot")

            await client.close()
            await result_queue.put(result)
            
        except Exception as e:
            logging.exception(f"[{token_preview}] on_ready exception: {e}")
            result["errors"].append(f"on_ready exception: {e}")
            try:
                await client.close()
            except:
                pass
            await result_queue.put(result)

    try:
        await client.start(token)
    except Exception as e:
        logging.exception(f"[{token_preview}] start/connection error: {e}")
        result["errors"].append(f"start error: {e}")
        try:
            await client.close()
        except:
            pass
        await result_queue.put(result)

def distribute_users_among_bots(all_user_ids: Set[int], num_bots: int) -> List[List[int]]:
    """
    Distribute users evenly among bots so no user gets duplicate DMs.
    """
    user_list = list(all_user_ids)
    buckets = [[] for _ in range(num_bots)]
    
    # Round-robin distribution
    for i, user_id in enumerate(user_list):
        buckets[i % num_bots].append(user_id)
    
    return buckets

async def dm_all_users_flow():
    """Handle the DM all users workflow with no duplicates"""
    print(f"{WHITE}=== DM All Users in Server (No Duplicates) ==={RESET}")
    
    # Get tokens from user input
    tokens = get_tokens_from_input()
    if not tokens:
        print(f"{WHITE}No tokens provided. Returning to menu.{RESET}")
        return
    
    # Get server ID
    guild_id_raw = input(f"\n{WHITE}Enter the server (guild) ID to DM all users: {RESET}").strip()
    if not guild_id_raw.isdigit():
        print(f"{WHITE}Guild ID must be numeric.{RESET}")
        return
    guild_id = int(guild_id_raw)

    # Get message
    message_text = input(f"\n{WHITE}Enter the message to send to all users: {RESET}").strip()
    if not message_text:
        print(f"{WHITE}Empty message; aborting.{RESET}")
        return

    print(f"\n{WHITE}Starting process...{RESET}")
    print(f"{WHITE}Step 1: Fetching all users from server {guild_id}{RESET}")
    print(f"{WHITE}Step 2: Distributing users evenly among {len(tokens)} bots{RESET}")
    print(f"{WHITE}Step 3: Sending DMs with no duplicates{RESET}")
    print(f"{WHITE}Message: {message_text}{RESET}")

    # Step 1: Fetch all users from the server using first available bot
    print(f"\n{WHITE}=== Fetching Users from Server ==={RESET}")
    fetch_queue = asyncio.Queue()
    fetch_tasks = []
    
    # Try each bot until we find one that can fetch users
    all_user_ids = set()
    successful_fetch = False
    
    for token in tokens:
        fetch_tasks.append(asyncio.create_task(
            fetch_all_users_from_guild(token, guild_id, fetch_queue)
        ))
        break  # Just use first bot for fetching
    
    # Wait for fetch results
    for _ in range(len(fetch_tasks)):
        fetch_result = await fetch_queue.get()
        if fetch_result["is_member"] and fetch_result["user_ids"]:
            all_user_ids = fetch_result["user_ids"]
            successful_fetch = True
            print(f"{WHITE}Successfully fetched {len(all_user_ids)} users from server{RESET}")
            break
    
    # Wait for remaining fetch tasks to complete
    await asyncio.gather(*fetch_tasks, return_exceptions=True)
    
    if not successful_fetch or not all_user_ids:
        print(f"{WHITE}Failed to fetch users from server. Make sure bots are members of the server.{RESET}")
        return

    # Step 2: Distribute users evenly among all bots
    user_assignments = distribute_users_among_bots(all_user_ids, len(tokens))
    
    print(f"{WHITE}Distributed {len(all_user_ids)} users among {len(tokens)} bots:{RESET}")
    for i, assignment in enumerate(user_assignments):
        print(f"{WHITE}  Bot {i+1}: {len(assignment)} users{RESET}")

    # Step 3: Send DMs with assigned users
    print(f"\n{WHITE}=== Sending DMs ==={RESET}")
    dm_queue = asyncio.Queue()
    dm_tasks = []
    
    # Limit concurrent connections
    max_concurrent_connections = min(3, len(tokens))
    sem = asyncio.Semaphore(max_concurrent_connections)

    async def wrapper(token, assigned_users):
        async with sem:
            await dm_assigned_users(token, assigned_users, message_text, dm_queue, per_message_delay=2.0)

    # Start all bots with their assigned users
    for i, token in enumerate(tokens):
        assigned_users = user_assignments[i] if i < len(user_assignments) else []
        dm_tasks.append(asyncio.create_task(wrapper(token, assigned_users)))

    # Collect results
    results = []
    total_sent = 0
    total_failed = 0
    total_assigned = 0
    
    print(f"{WHITE}\n=== Bots Sending DMs ==={RESET}")
    for _ in range(len(dm_tasks)):
        res = await dm_queue.get()
        results.append(res)
        
        tp = res["token_preview"]
        status = f"{WHITE}[{tp}] "
        if res["connected"]:
            status += f"assigned={res['assigned_count']} sent={res['dm_sent']} failed={res['dm_failed']}"
        else:
            status += "CONNECTION_FAILED"
        
        if res["errors"]:
            status += f" errors={len(res['errors'])}"
        
        status += f"{RESET}"
        print(status)
        
        total_sent += res["dm_sent"]
        total_failed += res["dm_failed"]
        total_assigned += res["assigned_count"]

    # Wait for all tasks to finish
    await asyncio.gather(*dm_tasks, return_exceptions=True)

    # Final report
    print(f"{WHITE}\n=== FINAL REPORT ==={RESET}")
    print(f"{WHITE}Total Users in Server: {len(all_user_ids)}{RESET}")
    print(f"{WHITE}Total Users Assigned: {total_assigned}{RESET}")
    print(f"{WHITE}Total DMs Sent: {total_sent}{RESET}")
    print(f"{WHITE}Total DMs Failed: {total_failed}{RESET}")
    if total_assigned > 0:
        print(f"{WHITE}Success Rate: {(total_sent/total_assigned)*100:.1f}%{RESET}")
    else:
        print(f"{WHITE}Success Rate: 0%{RESET}")
    
    # Verify no duplicates
    if total_sent + total_failed == len(all_user_ids):
        print(f"{WHITE}✅ No duplicate DMs - each user was assigned to exactly one bot{RESET}")
    else:
        print(f"{WHITE}⚠️  Some users may have been missed or duplicated{RESET}")

    # Save detailed report
    with open("dm_no_duplicates_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"{WHITE}Detailed report saved to dm_no_duplicates_report.json{RESET}")

async def main():
    try:
        while True:
            display_menu()
            choice = input(f"{WHITE}Select an option (1-2): {RESET}").strip()
            
            if choice == "1":
                await dm_all_users_flow()
            elif choice == "2":
                print(f"{WHITE}Goodbye!{RESET}")
                break
            else:
                print(f"{WHITE}Invalid option. Please select 1 or 2.{RESET}")
                continue
            
            input(f"{WHITE}\nPress Enter to continue...{RESET}")
    except KeyboardInterrupt:
        print(f"\n{WHITE}Interrupted by user. Goodbye!{RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{WHITE}Interrupted by user. Goodbye!{RESET}")
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            print(f"{WHITE}Script finished successfully.{RESET}")
        else:
            raise
