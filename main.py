#!/usr/bin/python3

# pip install pyTelegramBotAPI

import os
import subprocess
import telebot
import re

allowed_user_ids = [
    172222663,  # GiovanniRN5
    690187343,  # lostark13
    419006851,  # dereference
]

# Read the Telegram token from the file
token_file = ".tgtoken"
with open(token_file, "r") as file:
    bot_token = file.read().strip()

bot = telebot.TeleBot(bot_token)


def is_valid_url(url):
    regex = re.compile(
        r"^(https?:\/\/)?(www\.)?([^\s.]+\.\S{2,}|localhost[\:?\d]*)\S*$"
    )
    return re.match(regex, url)


@bot.message_handler(commands=["alive"])
def check_alive(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "I'm alive and ready to go!")


@bot.message_handler(commands=["dump"])
def dump(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    file_path = ".github/workflows/dump.yml"

    if user_id not in allowed_user_ids:
        bot.send_message(chat_id, "You are not authorized to use this command.")
        return

    # Extract the url from the message
    dump_url = (
        message.text.split(" ", 1)[1].strip()
        if len(message.text.split(" ", 1)) > 1
        else ""
    )

    if not is_valid_url(dump_url):
        bot.send_message(chat_id, "Invalid URL provided.")
        return

    try:
        with open(file_path, "r") as file:
            lines = file.readlines()

        with open(file_path, "w") as file:
            for line in lines:
                if line.startswith("  DUMP_URL:"):
                    line = f'  DUMP_URL: "{dump_url}" # Direct url to a recovery zip\n'
                file.write(line)

        # Commit and push the changes
        subprocess.run(["git", "add", "."])
        subprocess.run(["git", "commit", "-m", dump_url, "--no-gpg-sign", "--allow-empty"])
        subprocess.run(["git", "push"])

        bot.send_message(chat_id, "Dump started successfully!")
        bot.send_message(
            chat_id,
            "Feel free to check the dump progress [here](https://github.com/Jiovanni-dump/dumpyara/actions)",
            parse_mode="Markdown",
        )
    except Exception as e:
        bot.send_message(chat_id, f"An error occurred: {str(e)}")

if __name__ == '__main__':
    bot.polling()
