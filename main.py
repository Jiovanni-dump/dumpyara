#!/usr/bin/python3

import os
import re
import time

import telebot
from requests import get, post
from requests.exceptions import ReadTimeout

from config import (
    allowed_user_ids,
    github_repo,
    github_token,
    tg_token,
    workflow_id,
)

bot = telebot.TeleBot(tg_token)


def is_valid_url(url):
    regex = re.compile(
        r'^(https?:\/\/)?(www\.)?([^\s.]+\.\S{2,}|localhost[\:?\d]*)\S*$'
    )
    return re.match(regex, url)


@bot.message_handler(commands=['alive'])
def check_alive(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "I'm alive and ready to go!")


@bot.message_handler(commands=['cancel'])
def cancel_run(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if user_id not in allowed_user_ids:
        bot.send_message(chat_id, 'You are not authorized to use this command.')
        return

    # Extract the run ID from the message
    run_id = (
        message.text.split(' ', 1)[1].strip()
        if len(message.text.split(' ', 1)) > 1
        else ''
    )

    if not run_id.isdigit():
        bot.send_message(chat_id, 'Invalid run ID provided.')
        return

    # Prepare the request to cancel the workflow run
    url = f'https://api.github.com/repos/{github_repo}/actions/runs/{run_id}/cancel'
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {github_token}',
    }

    response = post(url, headers=headers)

    if response.status_code == 202:
        bot.send_message(
            chat_id,
            f'Run `{run_id}` cancellation initiated successfully.',
            parse_mode='Markdown',
            disable_web_page_preview=True,
        )
    else:
        bot.send_message(
            chat_id,
            f'Failed to cancel the run {run_id}: {response.text}',
            parse_mode='Markdown',
            disable_web_page_preview=True,
        )


@bot.message_handler(commands=['dump'])
def dump(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if user_id not in allowed_user_ids:
        bot.send_message(chat_id, 'You are not authorized to use this command.')
        return

    # Extract the URL from the message
    dump_url = (
        message.text.split(' ', 1)[1].strip()
        if len(message.text.split(' ', 1)) > 1
        else ''
    )

    if not is_valid_url(dump_url):
        bot.send_message(chat_id, 'Invalid URL provided.')
        return

    # Prepare the request to trigger the workflow_dispatch event
    url = f'https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_id}/dispatches'
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {github_token}',
    }
    payload = {
        'ref': 'master',
        'inputs': {'urls': dump_url},
    }

    response = post(url, headers=headers, json=payload)

    if response.status_code == 204:
        time.sleep(3)  # hack
        bot.send_message(chat_id, 'Dump started successfully!')

        # Fetch the latest workflow run to get the run_id
        runs_url = f'https://api.github.com/repos/{github_repo}/actions/runs'
        runs_response = get(runs_url, headers=headers)
        if runs_response.status_code == 200:
            runs_data = runs_response.json()
            if (
                'workflow_runs' in runs_data
                and len(runs_data['workflow_runs']) > 0
            ):
                run_id = runs_data['workflow_runs'][0]['id']
                run_url = (
                    f'https://github.com/{github_repo}/actions/runs/{run_id}'
                )
                bot.send_message(
                    chat_id,
                    f'Check the dump progress [here]({run_url})\nTo cancel this dump run: `/cancel {run_id}`',
                    parse_mode='Markdown',
                    disable_web_page_preview=True,
                )
            else:
                bot.send_message(chat_id, 'Failed to retrieve the run ID.')
        else:
            bot.send_message(
                chat_id,
                f'Failed to retrieve workflow runs: {runs_response.text}',
                disable_web_page_preview=True,
            )
    else:
        bot.send_message(
            chat_id,
            f'Failed to start the dump: {response.text}',
            disable_web_page_preview=True,
        )


if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=35)
            break
        except ReadTimeout as e:
            print(f'ReadTimeout occurred: {e}')
            time.sleep(1)
        except Exception as e:
            print(f'An unexpected error occurred: {e}')
            time.sleep(1)
