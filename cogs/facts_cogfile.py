import asyncio
import discord 
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import json
import random
from discord_servers_cogs import *


# Load the .env file
load_dotenv()


guilds_list = all_discord_servers


class facts_cog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot

    @commands.command(name="fact", aliases=["ft", "rf"], description="Gives a random fact.")
    async def fact(self, ctx:commands.Context) -> None:
        """
        |coroutine| Gives a random fact from a json file (no API). 

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        await ctx.typing()
        try:
            with open(r'data/factsfile.json', 'r', encoding="utf8") as file:
                data = json.load(file)
        except FileNotFoundError as e:
            print(f'fact command: {e}')
            return

        random_fact = random.choice(data['facts'])
        embed = discord.Embed(title='Here is your random fact!',description=f'{random_fact}' ,color=discord.Color.blurple())
        await ctx.send(embed=embed)


# Set up the cog for the bot
async def setup(bot):
    await bot.add_cog(facts_cog(bot), guilds=guilds_list) 

