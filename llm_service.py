import json
import discord
import logging
from PIL import Image
from io import BytesIO
from google import genai
from pydantic import BaseModel
from db_ops import get_aliases_dict

RECEIPT_PROMPT = """Here is a photo of a receipt. Create a JSON object where the keys are the names of the items and the values are the cost of the item including taxes and other fees listed if applicable such that all of the values add up to the total at the bottom of the receipt. Do not stack items. If an item is listed multiple times, make a new key for each instance of the item with a number appended to the end of the name. If an item has a quantity greater than 1, split it into multiple items with the same name and append a number to the end of each instance of the item. Ignore any items that are not food or drink, such as "cash" or "change". If there is a tip listed, ignore it. If there is a tax listed, include it in the price of the items. If there is no tax listed, assume that the prices already include tax. If there are any discounts or coupons listed, subtract them from the total and distribute the discount evenly across all items. Do not include any items that are not food or drink in the JSON object. Here is the receipt image:"""

def ACTOR_PROMPT(pre_tip, notes, diners, aliases_dict):
    return f"""
        You are a bill-splitting assistant for a Discord server.
        Here is a JSON object representing the items ordered at a restaurant and their prices including tax and tip: {pre_tip}. Here are some additional notes on how the order was split: {notes}. The diners' IDs are: {diners}. Assume that unspecified items are split between all diners.
        Create a new JSON object where the keys are the names of the people who ordered and the values are the total amount each person owes. Substitute all aliases with their Discord ID using this dictionary: {aliases_dict}, and use the diners' ID if there is no known alias for them. Do not make duplicate calls for the same user, and make sure all aliases have been looked up.
        Make sure that the sum of all the values is equal to the total at the bottom of the receipt, and all diners are included in the JSON object unless the notes specifiy otherwise.
        Explain your reasoning and add it as an item in the JSON object with the key "explanation".
    """

def ACTOR_PROMPT_CORRECTION(pre_tip, notes, diners, critic_explanation, aliases_dict):
    return f"""
        You are a bill-splitting assistant for a Discord server.
        Here is an incorrect JSON object representing the items ordered at a restaurant and their prices including tax and tip: {pre_tip}. Here are some additional notes on how the order was split: {notes}. The diners' IDs are: {diners}. Assume that unspecified items are split between all diners.
        Here is the reasoning as to why the JSON object is incorrect: {critic_explanation}.
        Create a new JSON object to represent the correct distribution of costs. Substitute all aliases with their Discord ID using this dictionary: {aliases_dict}, and use placeholder IDs for any unknown users. Do not make duplicate calls for the same user, and make sure all aliases have been looked up.
        Make sure that the sum of all the values is equal to the total at the bottom of the receipt, and all diners are included in the JSON object unless the notes specifiy otherwise.
        Explain your reasoning and add it as an item in the JSON object with the key "explanation".
    """

class CriticOutput(BaseModel):
    is_correct: bool
    explanation: str
    
    def __getitem__(self, key):
        return getattr(self, key)

def CRITIC_PROMPT(pre_tip, notes, diners, per_person, explanation, aliases_dict):
    return f"""
        Approach this as a logic problem.
        I am given a list of items in a receipt after tax: {pre_tip}, and some additional notes on how the order was split: {notes}. If there are no notes, assume all items were shared equally. The diners' IDs are: {diners}.
        I have a JSON object representing how much each person owes for the bill: {per_person}. This is my explanation of how I arrived at these totals: {explanation}
        Your task is to ensure that the JSON object with tax has the bill split according to the notes given, and that the sum of all diners' payments after tip is equal to the original total. Make sure all of the listed diners are included in the JSON object, unless the notes specifiy otherwise.
        Use this dictionary to substitute all aliases with their Discord ID if needed: {aliases_dict}.
        Elaborate on why it is correct or incorrect with respect to my explanation. You may ignore negligible rounding errors of up to 1 cent. 
        
        Return your results as a JSON with two keys: "is_correct" which is true or false, and "explanation" which is your reasoning. It may look like 
        <example-output>
        {{
            "is_correct": false,
            "explanation": "The total amount owed does not match the receipt total. User 123456789 is missing from the split."
        }}  
        </example-output>
    """

async def read_receipt(client: genai.Client, model: str, image: discord.Attachment):
    # Function to parse receipt image and return a dictionary of items and prices
    image_bytes = await image.read()
    receipt_image = Image.open(BytesIO(image_bytes))

    response = client.models.generate_content(
        model=model, contents=[RECEIPT_PROMPT, receipt_image]
    )
    # logging.info(f"LLM Response: {response.text[response.text.find('{'):response.text.rfind('}') + 1]}")  # Log the LLM response for debugging
    items = json.loads(response.text[response.text.find('{'):response.text.rfind('}') + 1])
    return items

async def query_llm(ctx, client: genai.Client, model: str,  pre_tip: dict, members: list[discord.Member], tip: str, notes: str):
    # Function to query the LLM with a prompt and return the response
    diners = [member.id for member in members]
    aliases_dict = await get_aliases_dict(ctx)
    correct = False
    critic_explanation = ""

    try:
        while not correct:
            # Send second prompt to split the bill
            if critic_explanation:
                contents = [ACTOR_PROMPT_CORRECTION(pre_tip, notes, diners, critic_explanation, aliases_dict)]
            else:
                contents = [ACTOR_PROMPT(pre_tip, notes, diners, aliases_dict)]
            actor_response = client.models.generate_content(
                model=model, contents=contents,
            )

            actor_response_text = actor_response.text
            # logging.info(f"Actor LLM Raw Response: {actor_response_text}")
            # logging.info(f"Actor LLM Response: {actor_response_text[actor_response_text.find('{'):actor_response_text.rfind('}') + 1]}")  # Log the LLM response for debugging
            result = json.loads(actor_response_text[actor_response_text.find('{'):actor_response_text.rfind('}') + 1])
            actor_explanation = result.pop("explanation")
            per_person = dict(result)

            # Third prompt to verify correctness
            critic_response = client.models.generate_content(
                model=model,
                contents=[CRITIC_PROMPT(pre_tip, notes, diners, per_person, actor_explanation, aliases_dict)],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": CriticOutput,
                }
            )
            
            critic_result = critic_response.parsed
            
            critic_explanation = critic_result['explanation']
            correct = critic_result['is_correct']

            # logging.info(f"Critic LLM Response: {critic_explanation}")  # Log the critic's explanation for debugging


        if tip[-1] != '%':
            tip_percent = float(tip) / sum(float(v) for v in pre_tip.values())
        else:
            tip_percent = int(tip.strip('%')) / 100
        for user in per_person:
            per_person[user] = float(per_person[user]) * (1 + tip_percent)
        return per_person
    except Exception as e:
        logging.error(f"Error querying LLM: {e}")
        await ctx.reply("There was an error processing the receipt. Please try again.")
        return {}