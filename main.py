#!/usr/bin/python3

# Deps:
# pip install pyTelegramBotAPI requests

from requests import post
from requests.exceptions import ReadTimeout

import os
import re
import telebot
import time

from config import github_repo, workflow_id, github_token

# Read the Telegram token from the file
token_file = ".tgtoken"
with open(token_file, "r") as file:
    bot_token = file.read().strip()

# Allowed user IDs for extra security
allowed_user_ids = [
    172222663,  # GiovanniRN5
    690187343,  # lostark13
    419006851,  # dereference
    1333498126,  # dreadnoughtOO7
    5493533726,  # You know who
]

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


@bot.message_handler(commands=["cancel"])
def cancel_run(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if user_id not in allowed_user_ids:
        bot.send_message(chat_id, "You are not authorized to use this command.")
        return

    # Extract the run ID from the message
    run_id = (
        message.text.split(" ", 1)[1].strip()
        if len(message.text.split(" ", 1)) > 1
        else ""
    )

    if not run_id.isdigit():
        bot.send_message(chat_id, "Invalid run ID provided.")
        return

    # Prepare the request to cancel the workflow run
    url = f"https://api.github.com/repos/{github_repo}/actions/runs/{run_id}/cancel"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {github_token}",
    }

    response = post(url, headers=headers)

    if response.status_code == 202:
        bot.send_message(chat_id, f"Run {run_id} cancellation initiated successfully.")
    else:
        bot.send_message(chat_id, f"Failed to cancel the run {run_id}: {response.text}")

@bot.message_handler(commands=["dump"])
def dump(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if user_id not in allowed_user_ids:
        bot.send_message(chat_id, "You are not authorized to use this command.")
        return

    # Extract the URL from the message
    dump_url = (
        message.text.split(" ", 1)[1].strip()
        if len(message.text.split(" ", 1)) > 1
        else ""
    )

    if not is_valid_url(dump_url):
        bot.send_message(chat_id, "Invalid URL provided.")
        return

    # Prepare the request to trigger the workflow_dispatch event
    url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_id}/dispatches"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {github_token}",
    }
    payload = {
        "ref": "master",
        "inputs": {"urls": dump_url},
    }

    response = post(url, headers=headers, json=payload)

    if response.status_code == 204:
        bot.send_message(chat_id, "Dump started successfully!")
        bot.send_message(
            chat_id,
            "Feel free to check the dump progress [here](https://github.com/Jiovanni-dump/dumpyara/actions)",
            parse_mode="Markdown",
        )
    else:
        bot.send_message(chat_id, f"Failed to start the dump: {response.text}")


if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=35)
            break
        except ReadTimeout as e:
            print(f"ReadTimeout occurred: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(1)
