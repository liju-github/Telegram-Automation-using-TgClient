from telethon.sync import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, UpdateUsernameRequest, EditAdminRequest, GetParticipantRequest
from telethon.tl.types import ChatAdminRights, ChannelParticipantAdmin
from telethon.errors import (
    ChatAdminRequiredError,
    UserNotParticipantError,
    UsernameOccupiedError,
    FloodWaitError,
    AdminsTooMuchError
)
import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=f'safeguard_setup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
)

class SafeguardSetupError(Exception):
    """Custom exception for Safeguard setup errors"""
    pass

async def verify_admin_rights(client, channel, bot_id):
    """Verify if bot has proper admin rights"""
    try:
        participant = await client(GetParticipantRequest(channel, bot_id))
        if not isinstance(participant.participant, ChannelParticipantAdmin):
            raise SafeguardSetupError("Safeguard bot is not an admin")
        return True
    except UserNotParticipantError:
        raise SafeguardSetupError("Safeguard bot is not in the channel/group")
    except Exception as e:
        raise SafeguardSetupError(f"Error verifying admin rights: {str(e)}")

async def get_full_admin_rights():
    """Get full admin rights configuration"""
    return ChatAdminRights(
        post_messages=True,
        edit_messages=True,
        delete_messages=True,
        ban_users=True,
        invite_users=True,
        pin_messages=True,
        add_admins=False,
        anonymous=False,
        manage_call=True,
        other=True
    )

async def setup_safeguard_system(api_id: str, api_hash: str, public_username: str, group_title: str, channel_title: str):
    """
    Set up complete Safeguard system with private group and public channel
    
    Args:
        api_id (str): Telegram API ID
        api_hash (str): Telegram API hash
        public_username (str): Username for public channel (without @)
        group_title (str): Title for private group
        channel_title (str): Title for public channel
    """
    client = None
    try:
        # Initialize client
        client = TelegramClient('session_name', api_id, api_hash)
        await client.start()

        if not await client.is_user_authorized():
            raise SafeguardSetupError("User not authorized. Please run the script with an authorized session.")

        logging.info("Starting Safeguard setup process")

        # 1. Create private group
        try:
            logging.info("Creating private group...")
            private_group = await client(CreateChannelRequest(
                title=group_title,
                about="Private discussion group",
                megagroup=True
            ))
            private_group_entity = private_group.chats[0]
            logging.info(f"Private group created: {group_title}")
        except Exception as e:
            raise SafeguardSetupError(f"Failed to create private group: {str(e)}")

        # 2. Create public channel
        try:
            logging.info("Creating public channel...")
            public_channel = await client(CreateChannelRequest(
                title=channel_title,
                about="Verification portal",
                megagroup=False
            ))
            channel_entity = public_channel.chats[0]
            logging.info(f"Public channel created: {channel_title}")
        except Exception as e:
            raise SafeguardSetupError(f"Failed to create public channel: {str(e)}")

        # 3. Set username for public channel
        try:
            await client(UpdateUsernameRequest(
                channel=channel_entity,
                username=public_username
            ))
            logging.info(f"Username set for public channel: @{public_username}")
        except UsernameOccupiedError:
            raise SafeguardSetupError(f"Username '{public_username}' is already taken")
        except Exception as e:
            raise SafeguardSetupError(f"Failed to set username: {str(e)}")

        # 4. Add Safeguard bot and set admin rights
        try:
            safeguard_bot = await client.get_input_entity("@SafeguardRobot")
            admin_rights = await get_full_admin_rights()

            # Add to private group
            await client(EditAdminRequest(
                channel=private_group_entity,
                user_id=safeguard_bot,
                admin_rights=admin_rights,
                rank="Safeguard Bot"
            ))
            
            # Verify private group admin rights
            await verify_admin_rights(client, private_group_entity, safeguard_bot)
            logging.info("Safeguard bot added as admin to private group")

            # Add to public channel
            await client(EditAdminRequest(
                channel=channel_entity,
                user_id=safeguard_bot,
                admin_rights=admin_rights,
                rank="Safeguard Bot"
            ))
            
            # Verify public channel admin rights
            await verify_admin_rights(client, channel_entity, safeguard_bot)
            logging.info("Safeguard bot added as admin to public channel")

        except ChatAdminRequiredError:
            raise SafeguardSetupError("You don't have sufficient rights to add admins")
        except AdminsTooMuchError:
            raise SafeguardSetupError("This channel/group has too many admins already")
        except Exception as e:
            raise SafeguardSetupError(f"Failed to set up Safeguard bot: {str(e)}")

        # 5. Send setup command and handle setup message
        try:
            # Send setup command
            await client.send_message(
                private_group_entity,
                "/setup@SafeguardRobot"
            )
            logging.info("Setup command sent to private group")

            # Wait for bot response
            retries = 3
            setup_message = None
            while retries > 0:
                await asyncio.sleep(2)
                async for message in client.iter_messages(private_group_entity, limit=1):
                    if "SafeguardRobot" in message.message:
                        setup_message = message
                        break
                if setup_message:
                    break
                retries -= 1

            if not setup_message:
                raise SafeguardSetupError("Failed to get setup message from Safeguard bot")

            # Forward to public channel
            await setup_message.forward_to(channel_entity)
            logging.info("Setup message forwarded to public channel")

        except Exception as e:
            raise SafeguardSetupError(f"Failed during setup message handling: {str(e)}")

        # 6. Generate and save invite links
        try:
            from telethon.tl.functions.messages import ExportChatInviteRequest
            
            private_invite = await client(ExportChatInviteRequest(
                peer=private_group_entity
            ))
            
            logging.info("Setup completed successfully!")
            print("\n=== SETUP COMPLETED SUCCESSFULLY ===")
            print(f"Public Channel: @{public_username}")
            print(f"Private Group Link: {private_invite.link}")
            print("\nNext Steps:")
            print("1. Visit your public channel to verify the setup")
            print("2. Configure Safeguard settings using the inline buttons")
            print("3. Test the verification system")
            print("\nCheck the log file for detailed setup information")

        except Exception as e:
            raise SafeguardSetupError(f"Failed to generate invite links: {str(e)}")

    except FloodWaitError as e:
        logging.error(f"Hit rate limit. Please wait {e.seconds} seconds")
        raise SafeguardSetupError(f"Rate limit hit. Please wait {e.seconds} seconds before trying again")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise
    finally:
        if client:
            await client.disconnect()

# Example usage
if __name__ == "__main__":
    # Configuration
    API_ID = "<---------->"
    API_HASH = "<---------->"
    PUBLIC_USERNAME = "<---------->"  # without @
    GROUP_TITLE = "Your Private Group Name"
    CHANNEL_TITLE = "Your Public Channel Name"
    
    try:
        asyncio.run(setup_safeguard_system(
            api_id=API_ID,
            api_hash=API_HASH,
            public_username=PUBLIC_USERNAME,
            group_title=GROUP_TITLE,
            channel_title=CHANNEL_TITLE
        ))
    except SafeguardSetupError as e:
        print(f"\nError during setup: {str(e)}")
        logging.error(f"Setup error: {str(e)}")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        logging.error(f"Unexpected error: {str(e)}")