import discord
from PIL import Image
import pytesseract
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
import json
import os

load_dotenv(find_dotenv())

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

async def read_receipt(attachment):
    # Function to read receipt image and update ledger.json
    items_json = ""
    return items_json

async def send_items(ctx, items_json):
    # Accepts a JSON string and sends each item to the Discord channel as a message
    receipt_items = json.loads(items_json)
    for item in receipt_items:
        await ctx.send(f"Item: {item}, Price: ${receipt_items[item]}")

@bot.event
async def on_reaction_add():
    


@bot.command()
async def receipt(ctx):
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            if attachment.filename.endswith('.jpg') or attachment.filename.endswith('.png'):
                # Parse and write to ledger.json
                await send_items(ctx, read_receipt(attachment))
    else:
        await ctx.send('Please upload your receipt image.')

@bot.command()
async def debt(ctx, arg: list[discord.Member] = None):
    if len(arg) == 2:
        member1, member2 = arg
        # Get the debt amount from ledger.json
        ctx.send(f'{member1.mention} owes {member2.mention} $.')
    else:
        await ctx.send('Specify two people to see money owed.')
bot.run(os.environ.get("DISCORD_TOKEN"))