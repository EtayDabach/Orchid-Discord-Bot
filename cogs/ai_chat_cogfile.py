import asyncio
import discord 
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime as dt
import openai

from discord_servers_cogs import *


# Load the .env file
load_dotenv()

guilds_list = all_discord_servers

# I am using a LLM model from OpenRouter because its free, but this set up works for OpenAI's chat GPT as well.

OPENROUTER_KEY = os.getenv('OPEN_ROUTER_KEY')


class chatbot_cog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        self.client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

        # Setting base personality 
        self.deafult_start = "You are name Orchid, and you are an AI companion."
        self.deafult_end = "Do not mention who you are acting like."

        # Store personality globally (default to Rem)
        self.bot_personality = "rem"

        self.personality_presets = {
            "rem": f"{self.deafult_start} You speaks and act like Rem from Re:Zero. You are kind, loyal, and deeply devoted to the person you admire. You are soft-spoken, but you will fiercely protect those you love. {self.deafult_end}",
            "ram": f"{self.deafult_start} You speaks and act like Ram from Re:Zero. You are sarcastic, blunt, and slightly arrogant. You often tease others, but deep down, you care for those close to you. {self.deafult_end}"
        }

        # Stores chat history per user
        self.conversation_history = {}  


    @commands.command(name="setpersonality", aliases=["personality"], help="Set the Orchid's personality (for now only Rem or Ram. Rem is deafult ofc).")
    async def setpersonality(self, ctx:commands.Context, choice:str) -> None:
        """
        |coroutine| Set the Orchid's personality (for now only Rem or Ram. Rem is deafult ofc).
        \n
        e.g:
        \n
        /personality {choice}

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            choice (str): Set rem or ram personality
        """
        choice = choice.lower()
        # Get user ID to track individual conversations
        user_id_str = str(ctx.author.id) # Useless for now...
        if choice in self.personality_presets:
            self.bot_personality = choice
            await ctx.send(embed=discord.Embed(title=f"Personality set to **{self.bot_personality}**!" ,color=discord.Color.blurple()))
        else:
            await ctx.send(embed=discord.Embed(title="Choose either **rem** or **ram**." ,color=discord.Color.blurple()))
            

    @commands.command(name="chat", aliases=["ai", "bot", "orchid"], help="Chat with Orchid.") # Might add a database to save the conversations...
    async def chat(self, ctx:commands.Context, *, message:str) -> None:
        """
        |coroutine| Chat with Orchid. Saves the last 15 messages, so Orchid could keep memory of the conversation. 
        Resets when the bot is shutdown. 
        \n
        e.g:
        \n
        /orchid {message}

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            message (str): Your message for the LLM.
        """
        await ctx.typing()

        # Get user ID to track individual conversations
        user_id_str = str(ctx.author.id)

        # Initialize history if user is chatting for the first time
        if user_id_str not in self.conversation_history:
            self.conversation_history[user_id_str] = [{"role": "system", "content": self.personality_presets[self.bot_personality]}]
        
        # Add the new user message to history
        self.conversation_history[user_id_str].append({"role": "user", "content": message}) # List

        try:
            # Differeny models of LLM:
            # "mistralai/mistral-small-3.1-24b-instruct:free"
            # "cognitivecomputations/dolphin3.0-r1-mistral-24b:free"

            response = self.client.chat.completions.create(
                model="mistralai/mistral-small-3.1-24b-instruct:free", 
                messages=self.conversation_history[user_id_str],  # Pass entire conversation history (List of two Dicts)
            )

            # reply = response["choices"][0]["message"]["content"] # for GPT
            reply = response.choices[0].message.content
            await ctx.send(embed=discord.Embed(description=f"{reply}" ,color=discord.Color.blurple()))

            # Save bot's response in history
            self.conversation_history[user_id_str].append({"role": "assistant", "content": reply}) # List of Dicts

            # Store only the last 15 exchanges
            MAX_HISTORY = 15
            if len(self.conversation_history[user_id_str]) > MAX_HISTORY:
                self.conversation_history[user_id_str] = self.conversation_history[user_id_str][-MAX_HISTORY:]

        except Exception as e:
            print(f'From chat command: {e}')
            await ctx.send(embed=discord.Embed(title='Something went wrong...', description=f'Please ask my admin to take a look at this problem.' ,color=discord.Color.blurple()))


    @commands.command(name="forget", aliases=["frgt"], help="Reset Orchid's memory form conversation history.")
    async def forget(self, ctx:commands.Context):
        """
        |coroutine| Reset Orchid's memory form conversation history.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        user_id_str = str(ctx.author.id)
        if user_id_str in self.conversation_history:
            del self.conversation_history[user_id_str]
            await ctx.send(embed=discord.Embed(title="Orchid has forgotten the conversation!" ,description="What are you hidding?", color=discord.Color.blurple()))
        else:
            await ctx.send(embed=discord.Embed(title="We haven't even started a conversation yet." ,description="You can ask me anything!", color=discord.Color.blurple()))


async def setup(bot):
    await bot.add_cog(chatbot_cog(bot), guilds=guilds_list) 
