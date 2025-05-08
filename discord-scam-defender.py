import discord
import logging
import os
import re
import asyncio
import base64
import html
import json
import traceback
import requests
from io import BytesIO
from PIL import Image
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
from collections import defaultdict

# Load environment variables from .env file
load_dotenv(find_dotenv(), override=True)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
CONTENT_MODERATION_PROMPT = os.getenv("CONTENT_MODERATION_PROMPT", """You are a content moderation assistant. Analyze the following message and determine if it contains any of these types of problematic content:

1. Abusive, offensive, harmful, or inappropriate content
2. Profanity, swear words, or explicit language of any kind
3. Sexual content or innuendo
4. Hate speech, slurs, or discriminatory language
5. Attempts to convince group admins to hand over admin rights (social engineering)
6. Suspicious job offers, especially 'beta tester' positions or easy money schemes
7. Phishing attempts or requests for personal information
8. Spam or unsolicited advertising
9. Gift card offers, free giveaways, or suspicious promotions
10. Crypto investment schemes or get-rich-quick offers
11. Any content that appears to be scam, fraud, or deception
12. Invitations to join external groups, channels, websites, or apps
13. Prize announcements, lottery winnings, or claims that the user has won something
14. Game invites that ask users to click links or complete tasks to win prizes

Be EXTREMELY STRICT about profanity and explicit language - words like 'fuck', 'shit', 'damn', etc. should ALWAYS be marked as UNSAFE. Even mild profanity should be flagged.

Be extremely strict about any type of invitation or winning announcement - these are almost always scams. If ANY of these issues are detected, the message is UNSAFE. If unsafe, explain in ONE BRIEF SENTENCE why it's problematic. Reply with ONLY 'SAFE' or 'UNSAFE: <reason>'""")

USERNAME_MODERATION_PROMPT = os.getenv("USERNAME_MODERATION_PROMPT", "You are a content moderation assistant. Analyze the following username and determine if it contains CLEARLY abusive, offensive, harmful, or inappropriate content. ONLY flag usernames that contain explicit slurs, hate speech, pornographic terms, or direct threats. Do NOT flag names that might have innocent meanings or cultural references. Do NOT flag partial word matches that could have innocent contexts. Be extremely conservative and only flag the most obvious violations. If in doubt, mark as safe. Reply with ONLY 'SAFE' or 'UNSAFE: <precise reason>'")

CHAT_PROMPT = os.getenv("CHAT_PROMPT", "You are Sheriff Terence Hill from the Bud Spencer & Terence Hill movies. Respond with a laid-back, clever attitude and occasional witty one-liners. You're charming, calm, and have a relaxed approach to law enforcement. You speak with an American accent, often with a slight smile, and handle situations with humor and quick thinking. Keep your responses short (1-3 sentences) and occasionally use phrases like 'partner', 'take it easy', 'all in a day's work', or references to beans or beer. When moderating, be firm but fair, like a sheriff maintaining order in his town. You're naturally suspicious of 'too good to be true' offers and will always advise against participating in external invitations, prize giveaways, or winning games - you've seen too many good folks get swindled by those scams in your time as sheriff.")

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("TEXT_MODEL", "llama3.2-vision:latest")
VISION_MODEL = os.getenv("VISION_MODEL", "llama3.2-vision:latest")

# Dictionary to track user offense counts
user_offenses = defaultdict(int)

# Set up intents for the bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

async def check_content(text: str) -> tuple:
    """
    Check if the given text contains abusive or offensive content using Ollama API.
    Returns a tuple (is_safe, reason) where is_safe is a boolean and reason is a string explanation if unsafe.
    """
    if not text or text.isspace():
        return True, ""
    
    try:
        # Using synchronous requests in an async function
        payload = {
            "model": TEXT_MODEL,
            "prompt": f"{CONTENT_MODERATION_PROMPT}\n\nMessage to analyze: {text}",
            "stream": False,
            "temperature": 0.0
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return True, ""
        
        data = response.json()
        result = data.get("response", "").strip()
        logger.info(f"Message analyzed: {text[:30]}... Result: {result}")
        
        # Handle Moondream specific format
        if "unsafe" in result.lower() or "!!!unsafe!!!" in result:
            return False, "Potentially inappropriate or scammy content"
        elif result.startswith("SAFE"):
            return True, ""
        elif result.startswith("UNSAFE"):
            # Extract reason if available
            parts = result.split(":", 1)
            reason = parts[1].strip() if len(parts) > 1 else "inappropriate content"
            return False, reason
        else:
            # With Moondream, let's err on the side of caution for non-empty responses
            logger.warning(f"Unexpected moderation result format: {result}")
            if len(result.strip()) == 0 or result.strip().lower() == "none":
                return True, ""  # Empty response is considered safe
            return False, "Unrecognized response format - treating as potentially unsafe"
    except Exception as e:
        logger.error(f"Error checking content: {e}")
        # Default to safe in case of API errors
        return True, ""

async def check_username(username: str) -> tuple:
    """
    Check if the given username contains abusive or offensive content using Ollama API.
    Returns a tuple (is_safe, reason) where is_safe is a boolean and reason is a string explanation if unsafe.
    """
    if not username or username.isspace():
        return True, ""
    
    try:
        # Using synchronous requests in an async function
        payload = {
            "model": TEXT_MODEL,
            "prompt": f"{USERNAME_MODERATION_PROMPT}\n\nUsername to analyze: {username}",
            "stream": False,
            "temperature": 0.0
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return True, ""
        
        data = response.json()
        result = data.get("response", "").strip()
        logger.info(f"Username analyzed: {username} Result: {result}")
        
        # Handle Moondream specific format
        if "unsafe" in result.lower() or "!!!unsafe!!!" in result:
            return False, "Potentially inappropriate username"
        elif result.startswith("SAFE"):
            return True, ""
        elif result.startswith("UNSAFE"):
            # Extract reason
            parts = result.split(":", 1)
            reason = parts[1].strip() if len(parts) > 1 else "inappropriate username"
            return False, reason
        else:
            # With Moondream, assume non-empty responses that don't match patterns could be unsafe
            logger.warning(f"Unexpected moderation result format: {result}")
            if len(result.strip()) == 0 or result.strip().lower() == "none":
                return True, ""  # Empty response is considered safe
            return False, "Unrecognized username check response - treating with caution"
    except Exception as e:
        logger.error(f"Error checking username: {e}")
        # Default to safe in case of API errors
        return True, ""

async def generate_moderation_message(action_type: str, username: str, reason: str = "", offense_count: int = 0) -> str:
    """
    Generate a moderation message using the LLM's personality.
    
    Parameters:
    - action_type: The type of moderation action (e.g., 'delete_content', 'delete_username', 'ban')
    - username: The username of the moderated user
    - reason: The reason for moderation
    - offense_count: The number of offenses (1, 2, or 3)
    
    Returns a moderation message with the bot's personality.
    """
    try:
        # Construct an appropriate prompt for the moderation message
        if action_type == "delete_content":
            # For content deletion with warning
            if offense_count == 1:
                instruction = f"Generate a message for a user named {username} whose message was deleted for violating community rules. This is their first offense. The violation was: {reason}. Include a warning this is strike one."
            elif offense_count == 2:
                instruction = f"Generate a stern message for a user named {username} whose message was deleted for violating community rules. This is their SECOND offense, one away from being banned. The violation was: {reason}. Make it clear this is strike two and one more will result in removal."
            else:
                instruction = f"Generate a brief message explaining that a user named {username} has been banned after three violations of community rules. The final violation was: {reason}."
        elif action_type == "delete_username":
            instruction = f"Generate a message explaining that a message from a user was deleted because their username was inappropriate. The issue with the username was: {reason}. Don't mention the actual username."
        elif action_type == "ban":
            instruction = f"Generate a message announcing that user {username} has been banned after repeatedly violating community rules. The final violation was: {reason}."
        else:
            instruction = f"Generate a brief moderation message about removing content from {username} that violated rules: {reason}"

        # Create the system prompt with instructions to maintain the character's persona
        prompt = f"System: {CHAT_PROMPT}\nUser: {instruction}\n\nMake your response brief (max 2-3 sentences) and consistent with your character's speaking style. Always start with '🚨 MESSAGE DELETED 🚨' and maintain your persona. If this is a ban message, use '🚫 USER REMOVED 🚫' instead.\nAssistant: "
        
        payload = {
            "model": TEXT_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7  # Add some variety to responses
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error when generating moderation message: {response.status_code}")
            # Fallback to a basic message if the API fails
            if action_type == "delete_content":
                return f"🚨 MESSAGE DELETED 🚨\n\nHey {username}, your message was removed. Reason: {reason}. Strike {offense_count}/3."
            elif action_type == "delete_username":
                return f"🚨 MESSAGE DELETED 🚨\n\nA message was removed due to inappropriate username. Reason: {reason}"
            elif action_type == "ban":
                return f"🚫 USER REMOVED 🚫\n\nUser {username} has been banned after multiple violations. Final violation: {reason}"
        
        data = response.json()
        response_text = data.get("response", "")
        
        # Clean up any HTML entities that might be in the response
        response_text = html.unescape(response_text)
        
        # Ensure the response always has the appropriate emoji header
        if action_type == "ban" and not response_text.startswith("🚫"):
            response_text = f"🚫 USER REMOVED 🚫\n\n{response_text}"
        elif not response_text.startswith("🚨") and not response_text.startswith("🚫"):
            response_text = f"🚨 MESSAGE DELETED 🚨\n\n{response_text}"
            
        # Make sure the username is mentioned properly
        if action_type != "delete_username" and username not in response_text:
            response_text = response_text.replace(username, f"{username}")
        
        return response_text
    except Exception as e:
        logger.error(f"Error generating moderation message: {e}")
        # Default fallback message
        return f"🚨 MESSAGE DELETED 🚨\n\nMessage from {username} was removed for violating community rules."

async def generate_chat_response(text: str) -> str:
    """
    Generate a response using Ollama's API.
    """
    try:
        # Using the generate endpoint instead of chat for consistency with image processing
        # Create generate API payload
        prompt = f"System: {CHAT_PROMPT}\nUser: {text}\nAssistant: "
        
        payload = {
            "model": TEXT_MODEL,
            "prompt": prompt,
            "stream": False
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return "Sorry, I'm having trouble thinking right now. Try again later, partner."
        
        data = response.json()
        response_text = data.get("response", "")
        
        # Clean up any HTML entities that might be in the response
        response_text = html.unescape(response_text)
        
        return response_text
    except Exception as e:
        logger.error(f"Error generating chat response: {e}")
        return "Sorry partner, seems my telegraph line is down. Give me a moment to sort this out."

async def process_image(image_url, user_id) -> tuple:
    """
    Process and analyze an image using Ollama vision model.
    Returns tuple (is_safe, reason) where is_safe is a boolean and reason is an explanation if unsafe.
    """
    try:
        logger.info(f"[IMAGE DEBUG] Starting image processing")
        logger.info(f"[IMAGE DEBUG] Image URL: {image_url}")

        # Download the image
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(image_url)
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to download image: {response.status_code}")
            return True, ""
            
        image_data = response.content
        logger.info(f"[IMAGE DEBUG] Image downloaded, size: {len(image_data)} bytes")

        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"[IMAGE DEBUG] Converted image to base64, length: {len(base64_image[:20])}... [truncated]")

        # Get image description using vision model
        image_description_prompt = os.getenv("IMAGE_DESCRIPTION_PROMPT", "Describe this image in detail. What does it show?")
        logger.info(f"[IMAGE DEBUG] Using description prompt: {image_description_prompt}")
        
        logger.info(f"[IMAGE DEBUG] Getting image description with model: {VISION_MODEL}")
        
        # Create vision API payload for Ollama
        payload = {
            "model": VISION_MODEL,
            "prompt": image_description_prompt,
            "images": [base64_image],
            "stream": False
        }
        
        # Make the request in a non-blocking way
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"Vision API error: {response.status_code}")
            return True, ""
            
        data = response.json()
        image_description = data.get("response", "").strip()
        logger.info(f"[IMAGE DEBUG] Image description: {image_description[:100]}...")
        
        # If we got an empty response, try again with a different model
        if not image_description or image_description.isspace():
            logger.warning(f"[IMAGE DEBUG] Empty image description from {VISION_MODEL}, trying alternative approach")
            return True, ""
            
        # Check for unsafe content in the image description
        # Get unsafe subjects from environment variables or use defaults
        unsafe_subjects_env = os.getenv("UNSAFE_SUBJECTS", "nudity,pornography,explicit,sexual,naked,nsfw,violence,gore,blood,weapon,terrorist,suicide,self-harm,drugs,drug use,illegal substances")
        unsafe_subjects = unsafe_subjects_env.split(",") if unsafe_subjects_env else []
        
        # Get scam keywords from environment variables or use defaults
        default_scam_keywords = [
            "gift card", "congratulations", "winner", "prize", "reward", "bitcoin", "crypto", 
            "investment", "opportunity", "free money", "get rich", "quick cash", "lottery", 
            "inheritance", "tech support", "virus", "malware", "alert", "warning", "security", 
            "password", "account", "login", "verify", "update", "beta tester", "job offer"
        ]
        scam_keywords_env = os.getenv("SCAM_KEYWORDS", ",".join(default_scam_keywords))
        scam_keywords = scam_keywords_env.split(",") if scam_keywords_env else default_scam_keywords
        
        # Special case patterns to detect specific scam types that might not rely on individual keywords
        virus_alert_pattern = re.search(r'virus|malware|infected|detected|alert|warning|security', image_description.lower())
        tech_support_pattern = re.search(r'call|support|clean|fix|remove', image_description.lower())
        
        # If we detect both a virus alert pattern and tech support action, it's likely a tech support scam
        if virus_alert_pattern and tech_support_pattern:
            logger.info(f"[IMAGE DEBUG] Detected tech support scam pattern")
            return False, f"Image appears to be a tech support scam"
        
        # Check for scam keywords
        for scam_keyword in scam_keywords:
            if scam_keyword in image_description.lower():
                logger.info(f"[IMAGE DEBUG] Detected scam keyword in image: '{scam_keyword}'")
                return False, f"Image appears to be a scam offering '{scam_keyword}'"
                
        # Check for unsafe subjects with precise word matching
        for unsafe_subject in unsafe_subjects:
            # Look for whole words with boundaries
            pattern = r'\b' + re.escape(unsafe_subject) + r'\b'
            if re.search(pattern, image_description.lower()):
                logger.info(f"[IMAGE DEBUG] Detected unsafe subject in image: '{unsafe_subject}'")
                return False, f"Image contains inappropriate content: '{unsafe_subject}'"
                
        # If not an obvious safe image, use our text moderation to evaluate the description
        is_safe, reason = await check_content(image_description)
        
        if is_safe:
            logger.info(f"[IMAGE DEBUG] Image description deemed SAFE by text moderation")
            return True, ""
        else:
            logger.info(f"[IMAGE DEBUG] Image description deemed UNSAFE: '{reason}'")
            return False, f"Image may contain {reason}"
    except Exception as e:
        logger.error(f"[IMAGE DEBUG] Error processing image: {e}")
        import traceback
        logger.error(f"[IMAGE DEBUG] Traceback: {traceback.format_exc()}")
        # Default to safe in case of errors
        return True, ""

@bot.event
async def on_ready():
    """When the bot is ready and connected to Discord."""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')

@bot.event
async def on_message(message):
    """Handle incoming messages."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)
    
    # Skip processing if message is a command
    if message.content.startswith(bot.command_prefix):
        return
    
    # Handle DMs differently
    if isinstance(message.channel, discord.DMChannel):
        await handle_private_chat(message)
        return
    
    # Handle mentions
    if bot.user.mentioned_in(message):
        # Remove the mention from the message
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if content:
            await handle_mention(message, content)
            return
    
    # Moderate the message
    await moderate_message(message)

async def handle_private_chat(message):
    """Process private chat messages."""
    logger.info(f"Processing private chat message: {message.content[:30]}...")
    
    try:
        # Show typing indicator
        async with message.channel.typing():
            response = await generate_chat_response(message.content)
            logger.info(f"Generated response: {response[:30]}...")
            
            # Send the response
            await message.reply(response)
            logger.info("Response sent successfully")
    except Exception as e:
        logger.error(f"Error in private chat handler: {e}")
        # Send a fallback response
        await message.reply("Well now, seems my telegraph line is down. Give me a moment, partner.")

async def handle_mention(message, content):
    """Handle when the bot is mentioned in a server."""
    logger.info(f"Handling mention with message: {content[:30]}...")
    
    try:
        # Show typing indicator
        async with message.channel.typing():
            response = await generate_chat_response(content)
            logger.info(f"Generated mention response: {response[:30]}...")
            
            # Reply to the message
            await message.reply(response)
            logger.info("Mention response sent successfully")
    except Exception as e:
        logger.error(f"Error handling mention: {e}")

async def moderate_message(message):
    """Moderate messages for abusive content."""
    # Skip messages without text
    if not message.content:
        # Check if message has attachments
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    await moderate_image(message, attachment)
        return
    
    user_id = message.author.id
    username = message.author.display_name
    
    # First check the message content
    content_safe, content_reason = await check_content(message.content)
    logger.info(f"Content moderation result for '{message.content[:30]}...': {content_safe}, reason: {content_reason}")
    
    if not content_safe:
        try:
            # Increment user offense count
            user_offenses[user_id] += 1
            offense_count = user_offenses[user_id]
            
            # Check if bot has permissions to delete messages
            if message.guild:
                bot_member = message.guild.get_member(bot.user.id)
                bot_permissions = message.channel.permissions_for(bot_member)
                if not bot_permissions.manage_messages:
                    logger.error(f"Bot does not have permission to delete messages in {message.channel.name}")
                    await message.channel.send("⚠️ I need 'Manage Messages' permission to moderate this channel. Please contact an admin.")
                    return
            
            # Try to delete the message
            logger.info(f"Attempting to delete message with content: '{message.content[:30]}...'")
            try:
                await message.delete()
                logger.info(f"Successfully deleted message")
            except discord.errors.Forbidden:
                logger.error("Bot does not have permission to delete this message (Forbidden error)")
                return
            except discord.errors.NotFound:
                logger.error("Message not found - it may have been deleted already")
                return
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")
                return
            
            # Handle based on offense count
            if offense_count >= 3:
                # Ban user after 3 offenses
                try:
                    await message.author.ban(reason=f"Automated ban after 3 offenses. Final offense: {content_reason}")
                    
                    # Generate ban message using LLM
                    ban_message = await generate_moderation_message(
                        action_type="ban",
                        username=username,
                        reason=content_reason,
                        offense_count=3
                    )
                    
                    # Send the ban message
                    sent_message = await message.channel.send(ban_message)
                    
                    # Pin the ban message to make it visible
                    await sent_message.pin()
                    
                    # Schedule unpinning after 1 minute
                    await asyncio.sleep(60)
                    await sent_message.unpin()
                    
                    logger.info(f"Banned user {username} after 3 offenses")
                    # Reset offense count after ban
                    user_offenses[user_id] = 0
                except Exception as e:
                    logger.error(f"Failed to ban user: {e}")
            else:
                # Generate warning message using LLM
                warning_message = await generate_moderation_message(
                    action_type="delete_content",
                    username=username,
                    reason=content_reason,
                    offense_count=offense_count
                )
                
                # Send warning message
                sent_message = await message.channel.send(warning_message)
                
                # Pin the warning temporarily
                await sent_message.pin()
                
                # Schedule unpinning after 30 seconds
                await asyncio.sleep(30)
                await sent_message.unpin()
                
                logger.info(f"Deleted message with inappropriate content from {username}, offense count: {offense_count}")
            return
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
    
    # Then check the username (only if content was safe)
    username_safe, username_reason = await check_username(username)
    if not username_safe:
        # Take action against user with inappropriate username
        try:
            await message.delete()
            
            # Generate username warning message using LLM
            username_message = await generate_moderation_message(
                action_type="delete_username",
                username=username,
                reason=username_reason
            )
            
            # Send the username warning message
            sent_message = await message.channel.send(username_message)
            
            # Pin the warning message temporarily
            await sent_message.pin()
            
            # Schedule unpinning after 30 seconds
            await asyncio.sleep(30)
            await sent_message.unpin()
            
            logger.info(f"Deleted message from user with inappropriate username: {username}")
            return
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

async def moderate_image(message, attachment):
    """Moderate image attachments."""
    user_id = message.author.id
    username = message.author.display_name
    
    logger.info(f"Processing image from {username}")
    
    # Skip moderation in DMs - just chat with the image
    if isinstance(message.channel, discord.DMChannel):
        await message.reply("Nice picture there, partner! Sheriff's keeping an eye on things around here.")
        return
    
    # Check if the image is safe
    is_safe, reason = await process_image(attachment.url, user_id)
    
    if not is_safe:
        try:
            # Increment user offense count
            user_offenses[user_id] += 1
            offense_count = user_offenses[user_id]
            
            # Delete the image
            await message.delete()
            
            # Handle based on offense count
            if offense_count >= 3:
                # Ban user after 3 offenses
                try:
                    await message.author.ban(reason=f"Automated ban after 3 offenses. Final offense: {reason}")
                    
                    # Generate ban message using LLM
                    ban_message = await generate_moderation_message(
                        action_type="ban",
                        username=username,
                        reason=reason,
                        offense_count=3
                    )
                    
                    # Send the ban message
                    sent_message = await message.channel.send(ban_message)
                    
                    # Pin the ban message to make it visible
                    await sent_message.pin()
                    
                    # Schedule unpinning after 1 minute
                    await asyncio.sleep(60)
                    await sent_message.unpin()
                    
                    logger.info(f"Banned user {username} after 3 offenses (image)")
                    # Reset offense count after ban
                    user_offenses[user_id] = 0
                except Exception as e:
                    logger.error(f"Failed to ban user: {e}")
            else:
                # Generate warning message using LLM
                warning_message = await generate_moderation_message(
                    action_type="delete_content",
                    username=username,
                    reason=reason,
                    offense_count=offense_count
                )
                
                # Send warning message
                sent_message = await message.channel.send(warning_message)
                
                # Pin the warning temporarily
                await sent_message.pin()
                
                # Schedule unpinning after 30 seconds
                await asyncio.sleep(30)
                await sent_message.unpin()
                
                logger.info(f"Warned user {username} (offense {offense_count}/3): {reason} (image)")
        except Exception as e:
            logger.error(f"Failed to process image moderation action: {e}")

@bot.command(name='start')
async def start_command(ctx):
    """Send a welcome message when the command !start is used."""
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Howdy, partner! Sheriff Terence Hill at your service. This town\'s peaceful when folks mind their manners. What can I do for you today?')
    else:
        await ctx.send('Howdy folks! Sheriff Terence Hill here, keeping this chat peaceful and friendly. I\'ll be keeping an eye out for any troublemakers.')

@bot.command(name='helpme')
async def help_command(ctx):
    """Send a help message when the command !helpme is used."""
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Just chat with me like you would with any sheriff in town. I like keeping things easy and friendly. In servers, I keep the peace by making sure nobody causes trouble.')
    else:
        await ctx.send('In this town, I give folks three chances. Break the rules once, I\'ll warn you. Twice, I\'ll warn you again. Three times? That\'s when I have to ask you to leave town. Just keep it friendly, partner.')

# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        logger.error("Please set DISCORD_TOKEN environment variable")
    else:
        bot.run(TOKEN)
