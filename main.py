import asyncio
import discord 
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from discord_servers_cogs import *


# Load the .env file
load_dotenv()


BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')


# Both are from discord_servers_cogs
guilds_list = all_discord_servers
cogs_list = cog_names


class CustomBot(commands.Bot):
    def __init__(self, *args, **kwargs) -> None:
        # Forward all arguments, and keyword-only arguments to commands.Bot
        super().__init__(*args, **kwargs)

    async def on_ready(self)-> None:
        all_guilds =[]
        for guild in self.guilds:
            all_guilds.append(guild)
        print(f'Logged on as {self.user} in {all_guilds}!')
        print('All set!')
       
        # For alternative initialization
        # for cogfile in cogs_list:
        #     await self.load_extension(f'cogs.{cogfile}')
        # print('Cogs are synced!')

        # try:
        #     for guild in guilds_list:
        #         synced = await self.tree.sync(guild=guild)
        #         print(f'Synced {len(synced)} commands to guild {guild}')

        # except Exception as e:
        #     print(f'Error syncing commands: {e}')


intents = discord.Intents.all()
bot = CustomBot(command_prefix='/', intents=intents)


# Useless for now
@bot.tree.command(name='sync', description='Admin only. Sync the commands', guilds=guilds_list)
async def sync(interaction:discord.Interaction) -> None: # ctx:commands.Context
    if interaction.user.id == int(ADMIN_ID): ## str to int       
        # bot.tree.clear_commands(guild=guild) # clear cached commands
        # print('Cleared chached commands')
        try:
            commands_list = await bot.tree.fetch_commands(guild=interaction.guild)
            await interaction.response.send_message(f'Commands are already synced, Found {len(commands_list)} registered slash commands.')
        except discord.HTTPException as e:
            print(e)
            await interaction.response.send_message(f'Failed to sync commands')
            return
        except Exception as e:
            print(e)
            return
        else:
            synced = await bot.tree.sync(guild=interaction.guild) 
            await interaction.response.send_message(f'Synced {len(synced)} commands to this guild')
    else:
        # print(ADMIN_ID, type(ADMIN_ID), type(int(ADMIN_ID)))
        # print(ctx.author.id, type(ctx.author.id))
        await interaction.response.send_message('You must be the owner to use this command!')

# Useless for now
@bot.tree.command(name="list_slash", description='Owner only. List all the slash commands.', guilds=guilds_list)
async def list_slash(interaction:discord.Interaction) -> None: # ctx:commands.Context
    if interaction.user.id == int(ADMIN_ID): ## str to int
        commands_list = await bot.tree.fetch_commands(guild=interaction.guild)
        for cmd in commands_list:
            print(f"Slash Command: {cmd.name}")
        await interaction.response.send_message(f'Found {len(commands_list)} registered slash commands.')
    else:
        await interaction.response.send_message('You must be the owner to use this command!')



# Main initialization
async def main():
    async with bot:
        print("Loading cogs...")
        for cogfile in cogs_list:
            await bot.load_extension(f'cogs.{cogfile}')
        print('Cogs are synced!')
        await bot.start(BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())


# Alternative initialization
# if __name__ == '__main__':
#     bot.run(BOT_TOKEN)

