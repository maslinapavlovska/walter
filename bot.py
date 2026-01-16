import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime
import logging
from services.ai_service import AIService
from services.history_api import HistoryAPI
from services.water_stops_service import WaterStopsService
from services.electricity_stops_service import ElectricityStopsService

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/walter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('walter')

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
TIMEZONE = os.getenv('TIMEZONE', 'America/New_York')

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize services
ai_service = AIService()
history_api = HistoryAPI()
water_stops_service = WaterStopsService()
electricity_stops_service = ElectricityStopsService()

# Initialize scheduler
scheduler = AsyncIOScheduler()

async def send_daily_history():
    """Send the daily history message with Victorian humor, followed by water stops"""
    try:
        logger.info("Starting daily history and water stops task")

        # Get channel
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            logger.error(f"Channel {CHANNEL_ID} not found")
            return

        # Get today's date
        today = datetime.now()
        month = today.month
        day = today.day

        # Fetch historical events
        events = await history_api.get_events_for_date(month, day)

        if events:
            # Select 10 interesting events
            selected_events = history_api.select_best_events(events, count=10)

            # Generate Victorian-style commentary
            content = await ai_service.generate_victorian_commentary(selected_events)

            # Send message with @here mention
            await channel.send(
                content,
                allowed_mentions=discord.AllowedMentions(everyone=True)
            )
            logger.info("Daily history message sent successfully")
        else:
            logger.warning("No historical events found for today")

        # Fetch and send water stops information
        logger.info("Fetching water stops for daily update")
        try:
            stops = await water_stops_service.get_water_stops()

            if stops:
                messages = water_stops_service.format_water_stops_message(stops)
                # Handle both single message and list of messages
                if isinstance(messages, list):
                    for msg in messages:
                        await channel.send(msg)
                else:
                    await channel.send(messages)
                logger.info(f"Daily water stops update sent - {len(stops)} stops")
            else:
                # Send "all clear" message
                message = water_stops_service.format_no_stops_message()
                await channel.send(message)
                logger.info("Daily water stops update sent - no stops")

        except Exception as water_error:
            logger.error(f"Error sending water stops in daily update: {water_error}", exc_info=True)
            # Don't fail the whole task if water stops fails
            await channel.send("_Apologies, couldn't fetch water stop information this morning. Do check manually._")

        # Fetch and send electricity stops information
        logger.info("Fetching electricity stops for daily update")
        try:
            electricity_stops = await electricity_stops_service.get_electricity_stops()

            if electricity_stops:
                messages = electricity_stops_service.format_electricity_stops_message(electricity_stops)
                # Handle both single message and list of messages
                if isinstance(messages, list):
                    for msg in messages:
                        await channel.send(msg)
                else:
                    await channel.send(messages)
                logger.info(f"Daily electricity stops update sent - {len(electricity_stops)} stops")
            else:
                # Send "all clear" message
                message = electricity_stops_service.format_no_stops_message()
                await channel.send(message)
                logger.info("Daily electricity stops update sent - no stops")

        except Exception as electricity_error:
            logger.error(f"Error sending electricity stops in daily update: {electricity_error}", exc_info=True)
            # Don't fail the whole task if electricity stops fails
            await channel.send("_Apologies, couldn't fetch electricity outage information this morning. Do check manually._")

    except Exception as e:
        logger.error(f"Error in daily history task: {e}", exc_info=True)

@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Setup daily scheduler
    tz = pytz.timezone(TIMEZONE)
    scheduler.add_job(
        send_daily_history,
        trigger=CronTrigger(
            hour=12,
            minute=10,
            timezone=tz
        ),
        id='daily_history',
        replace_existing=True,
        name='Daily History & Water Stops'
    )

    # Start scheduler
    if not scheduler.running:
        scheduler.start()
        logger.info(f"Scheduler started - Daily history & water stops at 12:10 {TIMEZONE}")

@bot.command(name='test_daily')
@commands.has_permissions(administrator=True)
async def test_daily(ctx):
    """Manually trigger the daily history post (admin only)"""
    await ctx.send("Generating daily history post...")
    await send_daily_history()
    await ctx.send("Daily history post sent!")

@bot.command(name='next_post')
async def next_post(ctx):
    """Check when the next post is scheduled"""
    job = scheduler.get_job('daily_history')
    if job:
        next_run = job.next_run_time
        await ctx.send(f"Next post scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        await ctx.send("No daily post scheduled")

@bot.command(name='check_water')
async def check_water(ctx):
    """Check for current water stop announcements"""
    await ctx.send("💧 Checking for water stops... (this may take a moment)")

    try:
        stops = await water_stops_service.get_water_stops()

        if stops:
            messages = water_stops_service.format_water_stops_message(stops)
            # Handle both single message and list of messages
            if isinstance(messages, list):
                for msg in messages:
                    await ctx.send(msg)
            else:
                await ctx.send(messages)
        else:
            message = water_stops_service.format_no_stops_message()
            await ctx.send(message)

        logger.info(f"Water stops check completed - found {len(stops)} stops")

    except Exception as e:
        logger.error(f"Error checking water stops: {e}", exc_info=True)
        await ctx.send("❌ Sorry, encountered an error while checking water stops. Please try again later.")

@bot.command(name='check_power')
async def check_power(ctx):
    """Check for current electricity outage announcements"""
    await ctx.send("Checking for electricity outages... (this may take a moment)")

    try:
        stops = await electricity_stops_service.get_electricity_stops()

        if stops:
            messages = electricity_stops_service.format_electricity_stops_message(stops)
            # Handle both single message and list of messages
            if isinstance(messages, list):
                for msg in messages:
                    await ctx.send(msg)
            else:
                await ctx.send(messages)
        else:
            message = electricity_stops_service.format_no_stops_message()
            await ctx.send(message)

        logger.info(f"Electricity stops check completed - found {len(stops)} stops")

    except Exception as e:
        logger.error(f"Error checking electricity stops: {e}", exc_info=True)
        await ctx.send("Sorry, encountered an error while checking electricity outages. Please try again later.")

@bot.command(name='walter_status')
async def status(ctx):
    """Check Walter's status"""
    embed = discord.Embed(
        title="Walter Bot Status",
        color=discord.Color.green()
    )
    embed.add_field(name="Status", value="🟢 Online", inline=True)
    embed.add_field(name="Guilds", value=len(bot.guilds), inline=True)
    embed.add_field(name="Scheduler", value="Running" if scheduler.running else "Stopped", inline=True)
    embed.add_field(name="Water Stops", value="Enabled", inline=True)
    embed.add_field(name="Electricity Stops", value="Enabled", inline=True)

    job = scheduler.get_job('daily_history')
    if job:
        embed.add_field(
            name="Next Post",
            value=job.next_run_time.strftime('%Y-%m-%d %H:%M %Z'),
            inline=False
        )

    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    else:
        logger.error(f"Command error: {error}", exc_info=True)
        await ctx.send("An error occurred while processing your command.")

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)
