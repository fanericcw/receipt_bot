import discord
from PIL import Image
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
import firebase_admin
from firebase_admin import db
import json
import os
import pandas as pd

load_dotenv(find_dotenv())

# Firebase setup
cred_obj = firebase_admin.credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
default_app = firebase_admin.initialize_app(cred_obj, {
    'databaseURL': os.environ.get("https://receipts-10876-default-rtdb.firebaseio.com/")
})

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='$', intents=intents)

async def read_receipt(attachment):
    # Function to read receipt image and return a json string of items and prices
    src = attachment.url
    #
    sample = pd.DataFrame()
    items_json = sample.to_json()
    return items_json

async def parse_reaction_message(message):
    msg_id = message.id
    price = float(message.content.split(", Price: $")[1])
    item = message.content.split(", Price: $")[0].split("Item: ")[1]
    original_msg = await message.channel.fetch_message(message.reference.message_id)
    creditor = original_msg.author
    return msg_id, item, price, creditor

async def add_to_ledger(msg_id, item, price, creditor, user):
    # Function to add item and price to ledger.json
    ref = db.reference(f'/{user.id}/{creditor.id}')
    data = {
        str(msg_id): {
            'item': item,
            'price': price,
        }
    }
    ref.set(data)

async def remove_from_ledger(msg_id, user, creditor):
    # Function to remove item and price from ledger.json
    ref = db.reference(f'/{user.id}/{creditor.id}')
    try:
        ref.child(str(msg_id)).remove()
    except Exception as e:
        print(f"Error removing from ledger: {e}. No action taken.")

@bot.event
async def on_reaction_add(reaction, user):
    # Upon an item is reacted to, add price to the ledger
    if reaction.message.author == bot.user:
        msg_id, item, price, creditor = await parse_reaction_message(reaction.message)
        # Update database with the item and price
        await add_to_ledger(msg_id, item, price, creditor, user)

@bot.event
async def on_reaction_remove(reaction, user):
    # Upon reaction being removed, remove price from the ledger
    if reaction.message.author == bot.user:
        msg_id, creditor = await parse_reaction_message(reaction.message)[0], await parse_reaction_message(reaction.message)[3]
        # Remove entry from database
        await remove_from_ledger(msg_id, user, creditor)

@bot.command()
async def receipt(ctx):
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            if attachment.filename.endswith('.jpg') or attachment.filename.endswith('.png'):
                items_json = await read_receipt(attachment)
                receipt_items = json.loads(items_json)
                for item in receipt_items:
                    await ctx.reply(f"Item: {item}, Price: ${receipt_items[item]}", mention_author=False)
    else:
        await ctx.reply('Please upload your receipt image.')

@bot.command()
async def debt(ctx, arg: list[discord.Member] = None):
    if len(arg) == 2:
        member1, member2 = arg
        # Get the debt amount from ledger.json
        ctx.reply(f'{member1.mention} owes {member2.mention} $.')
    else:
        await ctx.reply('Specify two people to see money owed.')
bot.run(os.environ.get("DISCORD_TOKEN"))