#!/usr/bin/python3

import json
import re
import socket
import time
import urllib.request
from urllib.parse import urlparse

import config


class TelegramBot:
    def __init__(self, token=config.TG_TOKEN):
        self.token = token
        self.base = f'https://api.telegram.org/bot{self.token}/'
        self.offset = 0
        self.handlers = {}

    def _request(self, method, data=None):
        url = self.base + method
        if data:
            data = json.dumps(data).encode()
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(url, data, headers)
        else:
            req = urllib.request.Request(url)

        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f'Request error: {e}')
            return {'ok': False}

    def send_message(self, chat_id, text, message_id=None):
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True,
        }
        if message_id:
            data['reply_to_message_id'] = message_id
        return self._request('sendMessage', data)

    def get_updates(self):
        return self._request(f'getUpdates?offset={self.offset + 1}&timeout=30')

    def cmd_handler(self, name, description=''):
        def decorator(func):
            self.handlers[f'/{name}'] = {
                'func': func,
                'description': description,
            }
            return func

        return decorator

    def set_commands(self):
        commands = []
        for cmd, handler in self.handlers.items():
            commands.append(
                {'command': cmd[1:], 'description': handler['description']}
            )
        self._request('setMyCommands', data={'commands': commands})

    def process(self):
        updates = self.get_updates().get('result', [])
        if not isinstance(updates, list):
            return

        for update in updates:
            self.offset = update['update_id']
            msg = update.get('message', {})
            text = msg.get('text', '').strip()

            if text and text.startswith('/'):
                cmd = text.split()[0].split('@')[0]
                if cmd in self.handlers:
                    self.handlers[cmd]['func'](msg)

    def start(self):
        self.set_commands()
        print('Bot started...')
        while True:
            self.process()
            time.sleep(0.5)


class GitHub:
    def __init__(
        self,
        token=config.GH_TOKEN,
        repo=config.GH_REPO,
        workflow_id=config.GH_WORKFLOW,
    ):
        self.token = token
        self.repo = repo
        self.workflow_id = workflow_id
        self.base = f'https://api.github.com/repos/{self.repo}/'

    def _request(self, method, endpoint, data=None):
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {self.token}',
        }
        url = self.base + endpoint

        if data:
            data = json.dumps(data).encode()
            req = urllib.request.Request(url, data, headers, method=method)
        else:
            req = urllib.request.Request(url, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as r:
                if r.status in (202, 204):  # GitHub success codes
                    return None
                return json.loads(r.read().decode())
        except Exception as e:
            print(f'GitHub error: {e}')
            return None

    def trigger_dump(self, url):
        response = self._request(
            'POST',
            f'actions/workflows/{self.workflow_id}/dispatches',
            {'ref': 'master', 'inputs': {'urls': url}},
        )

        if response is None:
            time.sleep(2)  # Allow GitHub to create the run
            return self.get_latest_run_id()
        return None

    def get_latest_run_id(self):
        response = self._request('GET', 'actions/runs?per_page=1')
        return (
            response['workflow_runs'][0]['id']
            if response and response.get('workflow_runs')
            else None
        )

    def cancel_dump(self, run_id):
        if not run_id.isdigit():
            return 'Invalid run ID'

        check_response = self._request('GET', f'actions/runs/{run_id}')
        if check_response is None:
            return 'Run ID not found'

        cancel_response = self._request('POST', f'actions/runs/{run_id}/cancel')
        return (
            'Cancellation initiated'
            if cancel_response is None
            else 'Failed to cancel'
        )


def validate_url(url):
    # Only allow URLs that start with http:// or https://
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False

    # Reject URLs ending with .tgz
    if url.lower().endswith('.tgz'):
        return False

    host = parsed.netloc.split(':')[0].lower()

    # Reject localhost and local addresses
    if (
        host == 'localhost'
        or host == '127.0.0.1'
        or host.startswith('192.168.')
        or host.startswith('10.')
        or host.startswith('172.')
        or host == '0.0.0.0'
        or host.startswith('169.254.')
        or host == '::1'
        or host.startswith('fc00:')
        or host.startswith('fd00:')
        or host.startswith('fe80:')
    ):
        return False

    # Reject specific hosts
    if 'picasion' in host or 'imgur' in host:
        return False

    # Validate URL format more strictly
    regex = re.compile(
        r'^https?:\/\/'  # must start with http:// or https://
        r'([A-Z0-9][A-Z0-9-]*(\.[A-Z0-9][A-Z0-9-]*)+)'  # domain (no localhost)
        r'(:[0-9]+)?'  # optional port
        r'(\/[^\s]*)?$',  # path
        re.IGNORECASE,
    )
    if not regex.match(url):
        return False

    # Ensure hostname is not empty and contains a dot
    if not host or '.' not in host:
        return False

    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False
    except Exception:
        return False


def main():
    bot = TelegramBot()
    github = GitHub()

    @bot.cmd_handler('dump', 'you should know')
    def send_dump_message(message):
        chat_id = message['chat']['id']
        message_id = message['message_id']
        user_id = message['from']['id']
        url = message['text'].split(' ', 1)[1] if ' ' in message['text'] else ''

        if user_id not in config.ADMINS:
            return bot.send_message(
                chat_id,
                '`ACCESS DENIED`',
                message_id=message_id,
            )

        if not url:
            return bot.send_message(
                chat_id,
                'Please provide a URL',
                message_id=message_id,
            )

        # Xiaomi hax
        if 'bigota' in url:
            url = url.replace('bigota', 'bn')

        if not validate_url(url):
            return bot.send_message(chat_id, 'Invalid or unreachable URL')

        run_id = github.trigger_dump(url)
        if run_id:
            run_url = f'https://github.com/{github.repo}/actions/runs/{run_id}'
            bot.send_message(
                chat_id,
                f'Dump started!\nTrack: [here]({run_url})\nCancel: `/cancel {run_id}`',
                message_id=message_id,
            )
        else:
            bot.send_message(
                chat_id,
                'Failed to start workflow',
                message_id=message_id,
            )

    @bot.cmd_handler('cancel', 'you should know')
    def send_cancel_message(message):
        chat_id = message['chat']['id']
        message_id = message['message_id']
        user_id = message['from']['id']
        run_id = (
            message['text'].split(' ', 1)[1] if ' ' in message['text'] else ''
        )

        if user_id not in config.ADMINS:
            return bot.send_message(
                chat_id,
                '`ACCESS DENIED`',
                message_id=message_id,
            )

        if not run_id:
            return bot.send_message(
                chat_id,
                'Please provide a run ID',
                message_id=message_id,
            )

        result = github.cancel_dump(run_id)
        bot.send_message(chat_id, result, message_id=message_id)

    bot.start()


if __name__ == '__main__':
    main()
