import discord
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Name the server as "SERVER_{1,2,3,4...}" in the .env file. Start with SERVER_1.

number_of_servers = 3 # Change according to the number of servers
all_discord_servers = []

for i in range(1, number_of_servers+1):
    server = discord.Object(id=os.getenv(f'SERVER_{i}'))
    all_discord_servers.append(server)


# print(all_discord_servers) # To check the list.

# Create a list of all the cogfiles in cogs. Only files that ends with "cogfile.py" will be added.
cog_names = []
for filename in os.listdir('./cogs'):
    if filename.endswith('cogfile.py'):
        cog_names.append(filename[:-3]) # Appends only the file name without .py

# print(cog_names)