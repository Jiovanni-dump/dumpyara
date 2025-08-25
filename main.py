#!/usr/bin/env PYTHONDONTWRITEBYTECODE=1 python3

import json
import time
import ssl
import urllib.request
from urllib.parse import urlparse

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import config


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

    def _request(self, method, endpoint, data=None):
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {self.token}',
        }
        url = f'https://api.github.com/repos/{self.repo}/{endpoint}'

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode() if data else None,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req) as r:
                if r.status in (202, 204):
                    return None
                return json.loads(r.read().decode())
        except Exception as e:
            print(f'GitHub error: {e}')
            return None

    def trigger_dump(self, url):
        time.sleep(1)
        self._request(
            'POST',
            f'actions/workflows/{self.workflow_id}/dispatches',
            {'ref': 'master', 'inputs': {'urls': url}},
        )
        time.sleep(4)

        response = self._request('GET', 'actions/runs?per_page=1')
        if response and response.get('workflow_runs'):
            return response['workflow_runs'][0]['id']
        return None

    def cancel_dump(self, run_id):
        if not run_id.isdigit():
            return 'Invalid run ID'

        if self._request('GET', f'actions/runs/{run_id}') is None:
            return 'Run ID not found'

        self._request('POST', f'actions/runs/{run_id}/cancel')
        return 'Cancellation initiated'


def validate_url(url):
    # Check URL scheme
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, None

    # Block local addresses
    host = parsed.netloc.split(':')[0].lower()
    if not host or '.' not in host:
        return False, None

    # Define archive indicators
    archive_types = {
        'application/gzip',
        'application/octet-stream',
        'application/x-7z-compressed',
        'application/x-bzip2',
        'application/x-gtar-compressed',
        'application/x-gzip',
        'application/x-rar-compressed',
        'application/x-tar',
        'application/x-xz',
        'application/x-zip',
        'application/x-zip-compressed',
        'application/zip',
    }

    # Create SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Try HEAD first with mobile user agent
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Linux; Android 11; Pixel 5 Build/RQ3A.210705.001; wv) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
            'Chrome/91.0.4472.120 Mobile Safari/537.36'
        ),
        'Accept': '*/*',
        'Connection': 'keep-alive',
    }
    try:
        req = urllib.request.Request(url, headers=headers, method='HEAD')
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            content_type = response.headers.get('Content-Type', '').lower()
            if any(
                archive_type in content_type for archive_type in archive_types
            ):
                return True, content_type
        return False, content_type
    except Exception as e:
        # HEAD might not be allowed, try GET with same headers
        try:
            req = urllib.request.Request(url, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                content_type = response.headers.get('Content-Type', '').lower()
                if any(
                    archive_type in content_type
                    for archive_type in archive_types
                ):
                    return True, content_type
            return False, content_type
        except Exception as e2:
            # Try with curl user agent as last resort
            curl_headers = {
                'User-Agent': 'curl/7.68.0',
                'Accept': '*/*',
            }
            try:
                req = urllib.request.Request(
                    url, headers=curl_headers, method='HEAD'
                )
                with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                    content_type = response.headers.get(
                        'Content-Type', ''
                    ).lower()
                    if any(
                        archive_type in content_type
                        for archive_type in archive_types
                    ):
                        return True, content_type
                return False, content_type
            except Exception as e3:
                # Final attempt with curl user agent and GET
                try:
                    req = urllib.request.Request(
                        url, headers=curl_headers, method='GET'
                    )
                    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                        content_type = response.headers.get(
                            'Content-Type', ''
                        ).lower()
                        if any(
                            archive_type in content_type
                            for archive_type in archive_types
                        ):
                            return True, content_type
                    return False, content_type
                except Exception as e4:
                    print(
                        f'validate_url error: HEAD {e}, GET {e2}, curl HEAD {e3}, curl GET {e4}'
                    )
                    return False, None


class TelegramBot:
    def __init__(self, token=config.TG_TOKEN, admins=config.ADMINS):
        self.token = token
        self.admins = admins
        self.github = GitHub()
        self.application = None

    async def post_init(self, application: Application) -> None:
        commands = [
            BotCommand('dump', 'you should know'),
            BotCommand('cancel', 'you should know'),
        ]
        await application.bot.set_my_commands(commands)

    async def dump(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user.id not in self.admins:
            return

        url = ' '.join(context.args) if context.args else ''

        if not url:
            await update.message.reply_text('Please provide a URL')
            return

        is_valid, content_type = validate_url(url)
        if not is_valid:
            message = 'Invalid or unreachable URL'
            if content_type:
                message += f'\nContent-Type: {content_type}'
            await update.message.reply_text(message)
            return

        run_id = self.github.trigger_dump(url)
        if run_id:
            run_url = (
                f'https://github.com/{self.github.repo}/actions/runs/{run_id}'
            )
            await update.message.reply_text(
                f'Dump started!\nTrack: [here]({run_url})\nCancel: `/cancel {run_id}`',
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text('Failed to start workflow')

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user.id not in self.admins:
            return

        run_id = context.args[0] if context.args else ''

        if not run_id:
            await update.message.reply_text('Please provide a run ID')
            return

        result = self.github.cancel_dump(run_id)
        await update.message.reply_text(result)

    def run(self):
        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self.post_init)
            .build()
        )

        self.application.add_handler(CommandHandler('dump', self.dump))
        self.application.add_handler(CommandHandler('cancel', self.cancel))

        print('Bot started...')
        self.application.run_polling()


def main():
    bot = TelegramBot()
    bot.run()


if __name__ == '__main__':
    main()
