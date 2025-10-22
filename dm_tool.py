import discord
import asyncio
import os
import time
import random
from colorama import Fore, Style, init

init(autoreset=True)

TOKENS_FILE = "tokens.txt"

class StableBot:
    """Single bot instance with isolated event loop and failure handling"""
    def __init__(self, token, bot_id):
        self.token = token
        self.bot_id = bot_id
        self.client = None
        self.ready = False
        self.connected = False
        self.guilds = {}
        self.last_heartbeat = time.time()
        self.failed = False
        self.reconnect_attempts = 0
        self.max_reconnects = 3

    async def start(self):
        """Start this bot with comprehensive error handling"""
        try:
            intents = discord.Intents.all()
            self.client = discord.Client(intents=intents)

            @self.client.event
            async def on_ready():
                self.ready = True
                self.connected = True
                self.reconnect_attempts = 0
                self.last_heartbeat = time.time()
                # Cache guilds we're in
                for guild in self.client.guilds:
                    self.guilds[guild.id] = guild
                print(f"{Fore.GREEN}Bot {self.bot_id} ready: {self.client.user} ({len(self.guilds)} servers){Style.RESET_ALL}")

            @self.client.event
            async def on_disconnect():
                self.connected = False
                print(f"{Fore.YELLOW}Bot {self.bot_id} disconnected{Style.RESET_ALL}")

            @self.client.event
            async def on_error(event, *args, **kwargs):
                print(f"{Fore.RED}Bot {self.bot_id} error in {event}: {args}{Style.RESET_ALL}")

            await self.client.start(self.token)

        except discord.LoginFailure:
            print(f"{Fore.RED}Bot {self.bot_id} login failed - invalid token{Style.RESET_ALL}")
            self.failed = True
        except discord.HTTPException as e:
            print(f"{Fore.RED}Bot {self.bot_id} HTTP error: {e}{Style.RESET_ALL}")
            self.failed = True
        except discord.GatewayNotFound:
            print(f"{Fore.RED}Bot {self.bot_id} gateway not found{Style.RESET_ALL}")
            self.failed = True
        except discord.ConnectionClosed as e:
            print(f"{Fore.RED}Bot {self.bot_id} connection closed: {e}{Style.RESET_ALL}")
            self.failed = True
        except Exception as e:
            print(f"{Fore.RED}Bot {self.bot_id} unexpected error: {e}{Style.RESET_ALL}")
            self.failed = True

    async def check_health(self):
        """Check if bot is still healthy"""
        if self.failed:
            return False

        if not self.connected:
            return False

        # Check if we've had a recent heartbeat
        if time.time() - self.last_heartbeat > 120:  # 2 minutes without activity
            print(f"{Fore.YELLOW}Bot {self.bot_id} appears dead (no heartbeat){Style.RESET_ALL}")
            return False

        return self.ready and self.connected

    async def safe_send_dm(self, user, message):
        """Safely send DM with bot health checking"""
        if not await self.check_health():
            return False, "Bot offline"

        try:
            # Get or create DM channel
            dm_channel = user.dm_channel
            if dm_channel is None:
                dm_channel = await user.create_dm()

            # Send with timeout
            send_task = asyncio.create_task(dm_channel.send(message))
            await asyncio.wait_for(send_task, timeout=10.0)

            self.last_heartbeat = time.time()
            return True, "Success"

        except discord.Forbidden:
            return False, "DMs disabled"
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 5
                await asyncio.sleep(retry_after)
                return await self.safe_send_dm(user, message)
            return False, f"HTTP error: {e}"
        except (asyncio.TimeoutError, Exception) as e:
            return False, f"Send failed: {e}"

class DMTool:
    def __init__(self):
        self.sent_count = 0
        self.total_members = 0
        self.processed_members = set()
        self.bot_tokens = []
        self.bots = []
        self.logs = []
        self.current_task = None
        self.health_check_task = None

    def display_banner(self):
        banner = f"""{Fore.LIGHTMAGENTA_EX}
 ███▄    █  ██▓  ▄████   ▄████  ▄▄▄                                
 ██ ▀█   █ ▓██▒ ██▒ ▀█▒ ██▒ ▀█▒▒████▄                              
▓██  ▀█ ██▒▒██▒▒██░▄▄▄░▒██░▄▄▄░▒██  ▀█▄                            
▓██▒  ▐▌██▒░██░░▓█  ██▓░▓█  ██▓░██▄▄▄▄██                           
▒██░   ▓██░░██░░▒▓███▀▒░▒▓███▀▒ ▓█   ▓██▒                          
░ ▒░   ▒ ▒ ░▓   ░▒   ▒  ░▒   ▒  ▒▒   ▓▒█░                          
░ ░░   ░ ▒░ ▒ ░  ░   ░   ░   ░   ▒   ▒▒ ░                          
   ░   ░ ░  ▒ ░░ ░   ░ ░ ░   ░   ░   ▒                             
         ░  ░        ░       ░       ░  ░                          

  ██████  ██▓▒██   ██▒     ██████ ▓█████ ██▒   █▓▓█████  ███▄    █ 
▒██    ▒ ▓██▒▒▒ █ █ ▒░   ▒██    ▒ ▓█   ▀▓██░   █▒▓█   ▀  ██ ▀█   █ 
░ ▓██▄   ▒██▒░░  █   ░   ░ ▓██▄   ▒███   ▓██  █▒░▒███   ▓██  ▀█ ██▒
  ▒   ██▒░██░ ░ █ █ ▒      ▒   ██▒▒▓█  ▄  ▒██ █░░▒▓█  ▄ ▓██▒  ▐▌██▒
▒██████▒▒░██░▒██▒ ▒██▒   ▒██████▒▒░▒████▒  ▒▀█░  ░▒████▒▒██░   ▓██░
▒ ▒▓▒ ▒ ░░▓  ▒▒ ░ ░▓ ░   ▒ ▒▓▒ ▒ ░░░ ▒░ ░  ░ ▐░  ░░ ▒░ ░░ ▒░   ▒ ▒ 
░ ░▒  ░ ░ ▒ ░░░   ░▒ ░   ░ ░▒  ░ ░ ░ ░  ░  ░ ░░   ░ ░  ░░ ░░   ░ ▒░
░  ░  ░   ▒ ░ ░    ░     ░  ░  ░     ░       ░░     ░      ░   ░ ░ 
      ░   ░   ░    ░           ░     ░  ░     ░     ░  ░         ░ 
                                             ░                     
{Style.RESET_ALL}"""
        print(banner)
        print("─" * 80)

    def load_tokens(self):
        """Load bot tokens from file"""
        try:
            with open(TOKENS_FILE, 'r') as f:
                content = f.read().strip()
                tokens = []
                for part in content.replace('\r', '\n').split('\n'):
                    for sub in part.split(','):
                        token = sub.strip()
                        if token:
                            tokens.append(token)

                self.bot_tokens = tokens
                return len(tokens) > 0
        except:
            return False

    async def start_bots_sequential(self):
        """Start bots one at a time to avoid conflicts"""
        if not self.load_tokens():
            print(f"{Fore.RED}No tokens found in {TOKENS_FILE}{Style.RESET_ALL}")
            return False

        print(f"{Fore.YELLOW}Starting {len(self.bot_tokens)} bots sequentially...{Style.RESET_ALL}")

        successful_bots = 0
        for i, token in enumerate(self.bot_tokens):
            try:
                bot = StableBot(token, i + 1)

                # Start with timeout
                start_task = asyncio.create_task(bot.start())
                try:
                    await asyncio.wait_for(start_task, timeout=30.0)
                    if not bot.failed:
                        self.bots.append(bot)
                        successful_bots += 1
                        print(f"{Fore.GREEN}Bot {i+1} started successfully{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Bot {i+1} failed to start{Style.RESET_ALL}")
                except asyncio.TimeoutError:
                    print(f"{Fore.RED}Bot {i+1} timed out during startup{Style.RESET_ALL}")
                    start_task.cancel()
                    bot.failed = True

                # Longer delay between starts
                await asyncio.sleep(5)

            except Exception as e:
                print(f"{Fore.RED}Failed to start Bot {i+1}: {e}{Style.RESET_ALL}")
                continue

        print(f"{Fore.CYAN}Successfully started: {successful_bots}/{len(self.bot_tokens)} bots{Style.RESET_ALL}")

        # Start health monitoring
        if successful_bots > 0:
            self.health_check_task = asyncio.create_task(self._health_monitor())

        return successful_bots > 0

    async def _health_monitor(self):
        """Continuously monitor bot health"""
        while True:
            try:
                online_bots = 0
                for bot in self.bots:
                    if await bot.check_health():
                        online_bots += 1
                    else:
                        if not bot.failed:
                            print(f"{Fore.YELLOW}Bot {bot.bot_id} is unhealthy, marking as failed{Style.RESET_ALL}")
                            bot.failed = True

                # Update display if DM campaign is running
                if self.current_task and not self.current_task.done():
                    await self.update_display()

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                print(f"{Fore.RED}Health monitor error: {e}{Style.RESET_ALL}")
                await asyncio.sleep(60)

    async def get_members_safe(self, server_id):
        """Safely get members from any available bot"""
        server_id_int = int(server_id)
        all_members = []

        for bot in self.bots:
            if not await bot.check_health():
                continue

            if server_id_int not in bot.guilds:
                continue

            guild = bot.guilds[server_id_int]

            try:
                # Method 1: Try cached members first
                if hasattr(guild, 'members') and guild.members:
                    members = [m for m in guild.members if not m.bot]
                    if members:
                        all_members = members
                        self.logs.append(f"{Fore.GREEN}Found {len(members)} members using Bot {bot.bot_id}{Style.RESET_ALL}")
                        break

                # Method 2: Try fetching members
                if hasattr(guild, 'fetch_members'):
                    try:
                        member_list = []
                        async for member in guild.fetch_members(limit=1000):
                            if not member.bot:
                                member_list.append(member)
                        all_members = member_list
                        self.logs.append(f"{Fore.GREEN}Fetched {len(member_list)} members using Bot {bot.bot_id}{Style.RESET_ALL}")
                        break
                    except Exception as e:
                        self.logs.append(f"{Fore.YELLOW}Fetch failed for Bot {bot.bot_id}: {e}{Style.RESET_ALL}")
                        continue

            except Exception as e:
                self.logs.append(f"{Fore.RED}Bot {bot.bot_id} member error: {e}{Style.RESET_ALL}")
                continue

        return all_members

    async def update_display(self):
        """Update the display"""
        os.system('cls' if os.name == 'nt' else 'clear')
        self.display_banner()

        # Count online bots
        online_bots = 0
        for bot in self.bots:
            if await bot.check_health():
                online_bots += 1
        total_bots = len(self.bots)
        
        print(f"{Fore.WHITE}DMs Sent: {Fore.CYAN}{self.sent_count}/{self.total_members}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Online Bots: {Fore.GREEN}{online_bots}/{total_bots}{Style.RESET_ALL}")

        # Show bot status
        statuses = []
        for bot in self.bots:
            if await bot.check_health():
                status = "🟢"
            else:
                status = "🔴"
            statuses.append(f"Bot {bot.bot_id}{status}")
        print(f"{Fore.WHITE}Status: {', '.join(statuses)}{Style.RESET_ALL}")

        print("─" * 80)

        print(f"{Fore.YELLOW}Recent Logs:{Style.RESET_ALL}")
        for log in self.logs[-10:]:
            print(log)

        print("─" * 80)

    async def mass_dm_stable(self, server_id, message):
        """Stable mass DM implementation with bot failure handling"""
        if self.current_task and not self.current_task.done():
            print(f"{Fore.RED}Already running a DM campaign!{Style.RESET_ALL}")
            return

        self.current_task = asyncio.create_task(self._run_mass_dm(server_id, message))

    async def _run_mass_dm(self, server_id, message):
        """Actual DM sending logic with bot failure resilience"""
        self.sent_count = 0
        self.processed_members.clear()
        self.logs.clear()

        print(f"{Fore.YELLOW}Starting DM campaign...{Style.RESET_ALL}")

        # Get available healthy bots
        available_bots = []
        for bot in self.bots:
            if await bot.check_health():
                available_bots.append(bot)
                
        if not available_bots:
            self.logs.append(f"{Fore.RED}No healthy bots available{Style.RESET_ALL}")
            await self.update_display()
            return

        self.logs.append(f"{Fore.GREEN}Using {len(available_bots)} healthy bots{Style.RESET_ALL}")

        # Get members
        all_members = await self.get_members_safe(server_id)
        if not all_members:
            self.logs.append(f"{Fore.RED}Could not fetch members from server {server_id}{Style.RESET_ALL}")
            await self.update_display()
            return

        self.total_members = len(all_members)
        await self.update_display()

        # Send DMs with bot failure handling
        success_count = 0
        failed_deliveries = 0

        for i, member in enumerate(all_members):
            if member.id in self.processed_members:
                continue

            # Get current healthy bots (they might have failed during the loop)
            current_healthy_bots = []
            for bot in available_bots:
                if await bot.check_health():
                    current_healthy_bots.append(bot)
                    
            if not current_healthy_bots:
                self.logs.append(f"{Fore.RED}All bots failed during campaign!{Style.RESET_ALL}")
                break

            # Distribute across available bots
            bot_index = i % len(current_healthy_bots)
            bot = current_healthy_bots[bot_index]

            success, reason = await bot.safe_send_dm(member, message)

            if success:
                success_count += 1
                self.sent_count = success_count
                self.processed_members.add(member.id)
                self.logs.append(f"{Fore.GREEN}Sent to {member.name} (Bot {bot.bot_id}){Style.RESET_ALL}")
            else:
                failed_deliveries += 1
                self.logs.append(f"{Fore.RED}Failed {member.name} - {reason}{Style.RESET_ALL}")

            await self.update_display()

            # Adaptive delay with jitter
            delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)

            # Check if we should continue based on failure rate
            if failed_deliveries > 20 and failed_deliveries / (success_count + failed_deliveries) > 0.8:
                self.logs.append(f"{Fore.RED}High failure rate, stopping campaign{Style.RESET_ALL}")
                break

        # Final results
        self.logs.append(f"{Fore.GREEN}Campaign complete: {success_count}/{len(all_members)} sent{Style.RESET_ALL}")
        if failed_deliveries > 0:
            self.logs.append(f"{Fore.YELLOW}Failed deliveries: {failed_deliveries}{Style.RESET_ALL}")
        await self.update_display()

    async def async_input(self, prompt):
        """Non-blocking input for async environments"""
        print(prompt, end='', flush=True)
        return await asyncio.get_event_loop().run_in_executor(None, input)

    async def shutdown(self):
        """Proper shutdown"""
        print(f"{Fore.YELLOW}Shutting down...{Style.RESET_ALL}")

        # Cancel health monitoring
        if self.health_check_task:
            self.health_check_task.cancel()

        # Cancel current task
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

        # Shutdown bots
        for bot in self.bots:
            try:
                if bot.client and not bot.client.is_closed():
                    await bot.client.close()
            except:
                pass

        await asyncio.sleep(2)
        print(f"{Fore.GREEN}Shutdown complete{Style.RESET_ALL}")

async def main():
    tool = DMTool()

    try:
        tool.display_banner()

        # Start bots
        if not await tool.start_bots_sequential():
            await tool.async_input("Press Enter to exit...")
            return

        # Main loop
        while True:
            print(f"\n{Fore.CYAN}Ready for DM campaign{Style.RESET_ALL}")

            # Get inputs
            server_id = await tool.async_input(f"{Fore.WHITE}>> Enter server ID: {Style.RESET_ALL}")
            if not server_id or not server_id.isdigit():
                print(f"{Fore.RED}Invalid server ID!{Style.RESET_ALL}")
                continue

            message = await tool.async_input(f"{Fore.WHITE}>> Enter DM message: {Style.RESET_ALL}")
            if not message:
                print(f"{Fore.RED}Message cannot be empty!{Style.RESET_ALL}")
                continue

            # Run campaign
            await tool.mass_dm_stable(server_id, message)

            # Wait for completion
            while tool.current_task and not tool.current_task.done():
                await asyncio.sleep(1)

            await tool.async_input(f"{Fore.WHITE}Press Enter to continue...{Style.RESET_ALL}")
            os.system('cls' if os.name == 'nt' else 'clear')
            tool.display_banner()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Shutdown requested...{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")
    finally:
        await tool.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
