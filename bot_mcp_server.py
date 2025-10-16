from typing import Any
import httpx
import logging
import firebase_admin
import os
from mcp.server.fastmcp import FastMCP
import discord

# Initialize FastMCP server
mcp = FastMCP("bot-mcp-server")

# Constants
USER_AGENT = "receipt-bot/1.0"

# Firebase setup
cred_obj = firebase_admin.credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
default_app = firebase_admin.initialize_app(cred_obj, {
    'databaseURL': os.environ.get("FIREBASE_DATABASE_URL")
})



if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')