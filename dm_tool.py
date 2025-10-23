#!/usr/bin/env python3
"""
main.py
- Loads bot tokens from tokens.txt
- Bots go online, you enter a server ID and message
- Bots will DM every user in that server automatically
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
    print(f"{WHITE}1. DM All Users in Server - Send DMs to every user in a server{RESET}")
    print(f"{WHITE}2. Exit{RESET}")
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

async def dm_all_users_in_guild(token: str, guild_id: int, message_text: str, result_queue: asyncio.Queue, per_message_delay: float = 2.0):
    """
    Connects a bot and DMs every user in the specified guild.
    """
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    token_preview = (token[:8] + "...") if token else "(empty)"
    result = {
        "token_preview": token_preview,
        "connected": False,
        "is_member": False,
        "users_fetched": 0,
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
            
            # Check guild membership and fetch members
            try:
                guild = await client.fetch_guild(guild_id)
                result["is_member"] = True
                logging.info(f"[{token_preview}] Bot is a member of guild {guild_id} (name: {getattr(guild, 'name', 'unknown')})")
                
                # Fetch all members from the guild
                logging.info(f"[{token_preview}] Fetching members from guild...")
                members = []
                async for member in guild.fetch_members(limit=None):
                    if not member.bot:  # Exclude bots
                        members.append(member)
                
                result["users_fetched"] = len(members)
                logging.info(f"[{token_preview}] Fetched {len(members)} users from guild")
                
                # DM each user
                if members:
                    logging.info(f"[{token_preview}] Starting to DM {len(members)} users...")
                    for i, member in enumerate(members):
                        try:
                            # Try to send DM
                            await member.send(message_text)
                            result["dm_sent"] += 1
                            logging.info(f"[{token_preview}] DM sent to {member} ({member.id}) - {i+1}/{len(members)}")
                            
                        except discord.Forbidden:
                            logging.warning(f"[{token_preview}] Cannot DM {member} (DMs closed)")
                            result["dm_failed"] += 1
                        except discord.HTTPException as he:
                            logging.warning(f"[{token_preview}] HTTP error DMing {member}: {he}")
                            result["dm_failed"] += 1
                        except Exception as e:
                            logging.exception(f"[{token_preview}] Error DMing {member}: {e}")
                            result["dm_failed"] += 1

                        # Rate limiting delay
                        await asyncio.sleep(per_message_delay)
                    
                    logging.info(f"[{token_preview}] Finished DMs. Sent: {result['dm_sent']}, Failed: {result['dm_failed']}")
                
            except discord.NotFound:
                result["is_member"] = False
                logging.warning(f"[{token_preview}] Bot is NOT a member of guild {guild_id}")
            except discord.Forbidden:
                result["errors"].append("Forbidden when fetching guild or members")
                logging.warning(f"[{token_preview}] Forbidden accessing guild {guild_id}")
            except Exception as e:
                result["errors"].append(f"Error: {e}")
                logging.exception(f"[{token_preview}] Error processing guild {guild_id}: {e}")

            # Properly close the client
            try:
                await client.close()
            except:
                pass
            await result_queue.put(result)
            
        except Exception as e:
            logging.exception(f"[{token_preview}] on_ready exception: {e}")
            result["errors"].append(f"on_ready exception: {e}")
            try:
                await client.close()
            except:
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
        try:
            await client.close()
        except:
            pass
        await result_queue.put(result)

async def dm_all_users_flow():
    """Handle the DM all users workflow"""
    print(f"{WHITE}=== DM All Users in Server ==={RESET}")
    
    tokens = load_tokens("tokens.txt")
    print(f"{WHITE}Loaded {len(tokens)} token(s).{RESET}")
    
    # Get server ID
    guild_id_raw = input(f"{WHITE}Enter the server (guild) ID to DM all users: {RESET}").strip()
    if not guild_id_raw.isdigit():
        print(f"{WHITE}Guild ID must be numeric.{RESET}")
        return
    guild_id = int(guild_id_raw)

    # Get message
    message_text = input(f"{WHITE}Enter the message to send to all users: {RESET}").strip()
    if not message_text:
        print(f"{WHITE}Empty message; aborting.{RESET}")
        return

    print(f"{WHITE}Starting process...{RESET}")
    print(f"{WHITE}Bots will fetch all users from server {guild_id} and send DMs{RESET}")
    print(f"{WHITE}Message: {message_text}{RESET}")

    result_queue = asyncio.Queue()
    tasks = []
    
    # Limit concurrent connections
    max_concurrent_connections = min(5, len(tokens))  # Reduced for stability
    sem = asyncio.Semaphore(max_concurrent_connections)

    async def wrapper(token):
        async with sem:
            await dm_all_users_in_guild(token, guild_id, message_text, result_queue, per_message_delay=2.0)

    # Start all bots
    for token in tokens:
        tasks.append(asyncio.create_task(wrapper(token)))

    # Collect results
    results = []
    total_sent = 0
    total_failed = 0
    total_users = 0
    
    for _ in range(len(tasks)):
        res = await result_queue.get()
        results.append(res)
        
        tp = res["token_preview"]
        print(f"{WHITE}[{tp}] members={res['users_fetched']} sent={res['dm_sent']} failed={res['dm_failed']} errors={len(res['errors'])}{RESET}")
        
        total_sent += res["dm_sent"]
        total_failed += res["dm_failed"]
        total_users += res["users_fetched"]

    # Wait for all tasks to finish
    await asyncio.gather(*tasks, return_exceptions=True)

    # Final report
    print(f"{WHITE}\n=== FINAL REPORT ==={RESET}")
    print(f"{WHITE}Total Users Found: {total_users}{RESET}")
    print(f"{WHITE}Total DMs Sent: {total_sent}{RESET}")
    print(f"{WHITE}Total DMs Failed: {total_failed}{RESET}")
    print(f"{WHITE}Success Rate: {(total_sent/max(total_users,1))*100:.1f}%{RESET}")

    # Save detailed report
    with open("dm_all_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"{WHITE}Detailed report saved to dm_all_report.json{RESET}")

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
