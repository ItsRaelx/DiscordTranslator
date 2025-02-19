import io
import discord
import aiohttp
import deepl  # Import the DeepL library
from googletrans import Translator  # Import googletrans
import os  # Import the 'os' module for environment variables

# Get variables from the environment
TOKEN = os.environ.get("DISCORD_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")

# Attempt to get TARGET_CHANNEL_ID from the environment,
# and convert it to an integer.  Provide a default value if
# the environment variable is not set or is invalid.
try:
    TARGET_CHANNEL_ID = int(os.environ.get("TARGET_CHANNEL_ID", 0))
except ValueError:
    print(
        "Warning: TARGET_CHANNEL_ID environment variable is not a valid integer."
        "  Using a default value of 0."
    )
    TARGET_CHANNEL_ID = 0  # Or some other appropriate default

# Check if required environment variables are set
if not all([TOKEN, WEBHOOK_URL, DEEPL_API_KEY, TARGET_CHANNEL_ID]):
    print(
        "Error: Missing one or more required environment variables:"
        " DISCORD_TOKEN, WEBHOOK_URL, DEEPL_API_KEY, TARGET_CHANNEL_ID"
    )
    exit()  # Exit the program if required variables are missing

# Set up intents to include message content
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Required for fetching guild information
intents.members = True  # Required for fetching member information

# Initialize the DeepL translator
deepl_translator = deepl.Translator(DEEPL_API_KEY)

# Initialize the Google Translate translator
google_translator = Translator()


class TranslationClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        # Only process messages from the specified channel.
        if message.channel.id != TARGET_CHANNEL_ID:
            return

        # Ignore messages from bots.
        if message.author.bot:
            return

        # Detect the language of the message using googletrans.
        try:
            detected = google_translator.detect(message.content)
            source_lang = detected.lang
        except Exception as e:
            print(f"Error detecting language: {e}")
            return

        # If the message is not in English, translate it using DeepL.
        if source_lang != "en":
            try:
                translated_text = deepl_translator.translate_text(
                    message.content, target_lang="EN-US"
                ).text
            except deepl.DeepLException as e:
                print(f"Error translating message: {e}")
                return

            # Handle attachments (images/files)
            attachment_files = []
            for attachment in message.attachments:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                file_content = await resp.read()
                                attachment_files.append(
                                    discord.File(
                                        io.BytesIO(file_content),
                                        filename=attachment.filename,
                                    )
                                )
                            else:
                                print(
                                    f"Failed to download attachment: {attachment.url} (Status: {resp.status})"
                                )
                except Exception as e:
                    print(f"Error downloading attachment: {e}")

            # Delete the original message.
            try:
                await message.delete()
            except discord.errors.Forbidden:
                print("Bot lacks permission to delete the message.")
                return
            except discord.errors.NotFound:
                print("Message not found (already deleted?)")
                return

            # Send the translated message via webhook with the original on a new line.
            async with aiohttp.ClientSession() as session:
                try:
                    webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
                except Exception as e:
                    print(f"Error creating webhook: {e}")
                    return

                try:
                    # The original message is appended on a new line,
                    # with "-#" for text formatting.
                    final_content = f"{translated_text}\n-# [Original] {message.content}"

                    await webhook.send(
                        content=final_content,
                        username=message.author.display_name,
                        avatar_url=(
                            message.author.avatar.url
                            if message.author.avatar
                            else message.author.default_avatar.url
                        ),
                        files=attachment_files,  # Re-upload the attachments
                    )
                except Exception as e:
                    print(f"Error sending webhook message: {e}")


client = TranslationClient(intents=intents)
client.run(TOKEN)
