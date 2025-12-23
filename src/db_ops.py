from firebase_admin import db
import discord
import logging

async def add_to_ledger(msg_id: int, item: str, price: float, guild: discord.Guild, user: discord.Member, creditor: discord.Member):
    # Function to add item and price to ledger.json
    ref = db.reference(f'/{guild.id}/{user.id}/{creditor.id}/{msg_id}')
    
    # Get existing items for this msg_id
    existing_data = ref.get()
    
    if existing_data is None:
        # First item for this message
        items = [{
            'item': item,
            'price': price,
        }]
    else:
        # Append to existing items
        items = existing_data if isinstance(existing_data, list) else []
        items.append({
            'item': item,
            'price': price,
        })
    
    # Save the updated list
    ref.set(items)

async def remove_from_ledger(msg_id: int, item: str, guild: discord.Guild, user: discord.Member, creditor: discord.Member):
    # Function to remove item and price from ledger.json
    ref = db.reference(f'/{guild.id}/{user.id}/{creditor.id}/{msg_id}')
    items = ref.get()
    if items:
        for i, item_data in enumerate(items):
            if item_data.get('item') == item:
                removed_item = items.pop(i)
                
                # Update the database
                if len(items) == 0:
                    ref.delete()
                else:
                    ref.set(items)
                # logging.info(f"Removed item: {removed_item}")
                return removed_item
            
async def remove_share_bill(msg_id: int, guild: discord.Guild):
    # Function to remove entire bill from ledger
    ref = db.reference(f'/{guild.id}')
    logging.info(f"Removing bill {msg_id} from ledger")
    snapshot = ref.get()
    if snapshot:
        for user_id, creditors in snapshot.items():
            if user_id != "aliases":  # Skip aliases node
                for creditor_id, bills in creditors.items():
                    if str(msg_id) in bills:
                        ref.child(f'{user_id}/{creditor_id}/{msg_id}').delete()
                        # logging.info(f"Removed bill {msg_id} for user {user_id} from creditor {creditor_id}")

async def fetch_user_user_debt(user: discord.Member, creditor: discord.Member, guild: discord.Guild) -> float:
    # Function to fetch a user's debt to a specified creditor from Firebase
    ref = db.reference(f'/{guild.id}/{user.id}/{creditor.id}')
    snapshot = ref.get()
    sum = 0.0
    if snapshot:
        for entry in snapshot.values():
            for item in entry:
                # logging.info(item)
                sum += item['price']
    return sum

async def fetch_user_debt(user: discord.Member, guild: discord.Guild) -> float:
    # Function to fetch a user's total debt in a server from Firebase
    ref = db.reference(f'/{guild.id}/{user.id}')
    snapshot = ref.get()
    sum = 0.0
    if snapshot:
        for creditor_id, debts in snapshot.items():
            for entry in debts.values():
                for item in entry:
                    # logging.info(item)
                    sum += item['price']
    return sum

# Util function for LLM to get aliases
async def get_aliases_dict(ctx) -> dict:
    ref = db.reference(f'/aliases/{ctx.guild.id}')
    snapshot = ref.get()
    if snapshot:
        aliases_dict = {v: k for k, v in snapshot.items()}
        # logging.info(f"Aliases dict: {aliases_dict}")  # Log the aliases dictionary for debugging
        return aliases_dict
    else:
        await ctx.reply("No aliases found in the database for this server.")