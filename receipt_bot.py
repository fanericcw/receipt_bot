import json
import os
import discord
from typing import Any
from PIL import Image
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
import firebase_admin
from firebase_admin import db
from google import genai
import firebase_admin
from firebase_admin import db, exceptions

load_dotenv(find_dotenv())

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='$', intents=intents)
bot.remove_command('help')

# Firebase setup
cred_obj = firebase_admin.credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
default_app = firebase_admin.initialize_app(cred_obj, {
    'databaseURL': os.environ.get("FIREBASE_DATABASE_URL")
})

# LLM setup
client = genai.Client(api_key=os.environ.get("GENAI_API_KEY"))
MODEL = "gemini-2.5-flash"
RECEIPT_PROMPT = """Here is a photo of a receipt. Create a JSON object where the keys are the names of the items and the values are the cost of the item including taxes and other fees listed if applicable such that all of the values add up to the total at the bottom of the receipt."""
def ACTOR_PROMPT(pre_tip, notes):
    return f"""
        Here is a JSON object representing the items ordered at a restaurant and their prices including tax and tip: {pre_tip}. Here are some additional notes on how the order was split: {notes}. Assume that unspecified items are split between all diners.
        Create a new JSON object where the keys are the names of the people who ordered and the values are the total amount each person owes. Make sure that the sum of all the values is equal to the total at the bottom of the receipt.
        Explain your reasoning and add it as an item in the JSON object with the key "explanation".
    """
def ACTOR_PROMPT_CORRECTION(pre_tip, notes, critic_explanation):
    return f"""
        Here is an incorrect JSON object representing the items ordered at a restaurant and their prices including tax and tip: {pre_tip}. Here are some additional notes on how the order was split: {notes}. Assume that unspecified items are split between all diners.
        Here is the reasoning as to why the JSON object is incorrect: {critic_explanation}.
        Create a new JSON object to arrive at the correct. Make sure that the sum of all the values is equal to the total at the bottom of the receipt.
        Explain your reasoning and add it as an item in the JSON object with the key "explanation".
    """
def CRITIC_PROMPT(pre_tip, notes, diners, per_person, explanation):
    return f"""
        Approach this as a logic problem.
        I am given a list of items in a receipt after tax: {pre_tip}, and some additional notes on how the order was split: {notes}. If there are no notes, assume all items were shared equally. The meal is shared between {diners}.
        I have a JSON object representing how much each person owes for the bill: {per_person}. This is my explanation of how I arrived at these totals: {explanation}
        Your task is to ensure that the JSON object with tax has the bill split according to the notes given, and that the sum of all diners' payments after tip is equal to the original total.
        Elaborate on why it is correct or incorrect with respect to my explanation. You may ignore negligible rounding errors of up to 1 cent. Return your results as a JSON with two keys: "is_correct" which is true or false, and "explanation" which is your reasoning.
    """

async def send_react_messages(dues, ctx):
    # Function to send messages for each item in the receipt with reaction options
    for item in dues.keys():
        price = dues[item]
        await ctx.send(f"Item: {item}, Price: ${price:.2f}.")

async def parse_reaction_message(message):
    msg_id = message.id
    price = float(message.content.split(", Price: $")[1])
    item = message.content.split(", Price: $")[0].split("Item: ")[1]
    original_msg = await message.channel.fetch_message(message.reference.message_id)
    creditor = original_msg.author
    return msg_id, item, price, creditor

async def read_receipt(image: discord.Attachment):
    # Function to parse receipt image and return a dictionary of items and prices
    image_bytes = await image.read()
    receipt_image = Image.open(image_bytes)

    response = client.models.generate_content(
        model=MODEL, contents=[RECEIPT_PROMPT, receipt_image]
    )
    items = json.loads(response.text)
    return items

async def query_llm(pre_tip: dict, members: list[discord.Member], tip: str, notes: str):
    # Function to query the LLM with a prompt and return the response
    diners = [member.name for member in members]
    correct = False
    critic_explanation = ""

    while not correct:
        # Send second prompt to split the bill
        if critic_explanation:
            actor_response = client.models.generate_content(
                model=MODEL, contents=[diners, ACTOR_PROMPT_CORRECTION(pre_tip, notes, critic_explanation)]
            )
        else:
            actor_response = client.models.generate_content(
                model=MODEL, contents=[diners, ACTOR_PROMPT(pre_tip, notes)]
            )
        result = json.loads(actor_response.text)
        actor_explanation = result.pop("explanation")
        per_person = dict(result)

        # Third prompt to verify correctness
        critic_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[CRITIC_PROMPT(pre_tip, notes, diners, per_person, actor_explanation)],
            config={
                "response_mime_type": "application/json",
            }
        )
        critic_result = json.loads(critic_response.text)
        correct = critic_result['is_correct']
        critic_explanation = critic_result['explanation']

    if tip[-1] != '%':
        tip_percent = float(tip) / sum(float(v) for v in pre_tip.values())
    else:
        tip_percent = int(tip.strip('%')) / 100
    print(tip_percent)
    for user in per_person:
        per_person[user] = float(per_person[user]) * (1 + tip_percent)
    return per_person

async def add_to_ledger(msg_id: int, item: str, price: float, user: discord.Member, creditor: discord.Member):
    # Function to add item and price to ledger.json
    ref = db.reference(f'/{user.id}/{creditor.id}')
    data = {
        str(msg_id): {
            'item': item,
            'price': price,
        }
    }
    ref.set(data)

async def remove_from_ledger(msg_id: int, user: discord.Member, creditor: discord.Member):
    # Function to remove item and price from ledger.json
    ref = db.reference(f'/{user.id}/{creditor.id}')
    try:
        ref.child(str(msg_id)).delete()
    except exceptions.FirebaseError as e:
        print(f"Error removing from ledger: {e}. No action taken.")

async def fetch_user_user_debt(user: discord.Member, creditor: discord.Member) -> float:
    # Function to fetch a user's debt to a specified creditor from Firebase
    ref = db.reference(f'/{user.id}/{creditor.id}')
    snapshot = ref.get()
    return sum(entry['price'] for entry in json.loads(snapshot.values())) if snapshot else 0.0

async def fetch_user_debt(user: discord.Member) -> float:
    # Function to fetch a user's total debt from Firebase
    ref = db.reference(f'/{user.id}')
    snapshot = ref.get()
    return sum(entry.values()['price'] for entry in json.loads(snapshot.values())) if snapshot else 0.0

async def fetch_user_owed(user: discord.Member) -> float:
    # Function to fetch the total amount owed to a user from Firebase
    ref = db.reference('/')
    snapshot = ref.get()
    total_owed = 0.0
    if snapshot:
        for creditor_id, debts in snapshot.items():
            if user.id in debts:
                total_owed += sum(entry['price'] for entry in json.loads(debts[user.id].values()))
    return total_owed

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.Member):
    # Upon an item is reacted to, add price to the ledger
    if reaction.message.author == bot.user:
        msg_id, item, price, creditor = await parse_reaction_message(reaction.message)
        # Update database with the item and price
        await add_to_ledger(msg_id, item, price, user, creditor)

@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.Member):
    # Upon reaction being removed, remove price from the ledger
    if reaction.message.author == bot.user:
        msg_id, creditor = await parse_reaction_message(reaction.message)[0], await parse_reaction_message(reaction.message)[3]
        # Remove entry from database
        await remove_from_ledger(msg_id, user, creditor)

@bot.command()
async def help(ctx):
    help_text = (
        "Commands:\n"
        "$receipt [mode] [tip] [notes] - Upload a receipt image and mention users to share with. Mode can be 'react' or 'due'. Add notes to specify how to split the bill.\n"
        "$due @user amount - Record that you owe a user a certain amount.\n"
        "$debt @user1 @user2 - Check how much user1 owes user2.\n"
    )
    await ctx.reply(help_text, mention_author=False)

@bot.command()
async def receipt(ctx,  mode: str = "react", tip: str = "", notes: str = ""):
    if not ctx.message.attachments:
        await ctx.reply('Please upload your receipt image.')
    elif not ctx.message.mentions:
        await ctx.reply('Please mention the user(s) you want to share the receipt with.')
    else:
        members = ctx.message.mentions + [ctx.message.author]
        images = [a for a in ctx.message.attachments if a.filename.lower().endswith(('.jpg', '.png'))]
        if not images:
            await ctx.reply('Please upload a valid image file (.jpg or .png).')
            return
        for image in images:
            if mode == "react":
                # Parse receipt image
                pre_tip = await read_receipt(image)
                # Send messages for each item in the receipt
                await send_react_messages(pre_tip, ctx)
            elif mode == "share":
                # Parse receipt image
                pre_tip = await read_receipt(image)
                # Send to LLM for processing
                await query_llm(pre_tip, members, tip, notes)
            else:
                await ctx.reply('Invalid mode. Use "react" or "share".')
                return

@bot.command()
async def due(ctx, member: discord.Member, amount: float):
    if amount > 0:
        # Update ledger with amount owed
        await ctx.reply(f'Updated {member.mention}\'s debt by ${amount}.')
    else:
        await ctx.reply('Amount must be positive.')

@bot.command()
async def owes(ctx, arg: list[discord.Member] = None):
    if len(arg) == 2:
        member1, member2 = arg
        debt_amount = await fetch_user_user_debt(member1, member2)
        ctx.reply(f'{member1.mention} owes {member2.mention} ${debt_amount}.')
    else:
        await ctx.reply('Specify two people to see money owed.')

bot.run(os.environ.get("DISCORD_TOKEN"))
