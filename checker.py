
import asyncio
import aiohttp
import os
import re
import signal
from tqdm.asyncio import tqdm_asyncio
from tortoise import Tortoise, run_async
from models.models import Link
from faker import Faker

fake = Faker()

class LinkChecker:
    def __init__(self, input_filename, account_file="dump\\accounts.txt", channel_file="dump\\channels.txt", chat_file="dump\\chats.txt", not_found_file="dump\\not_found.txt", db_path="sqlite://state/state.db"):
        self.input_filename = input_filename
        self.account_file = account_file
        self.channel_file = channel_file
        self.chat_file = chat_file
        self.not_found_file = not_found_file
        self.min_length = 5
        self.max_length = 32
        self.checked_links = set()
        self.db_path = db_path
        self.stat_lock = asyncio.Lock()

    async def init_db(self):
        await Tortoise.init(
            db_url=self.db_path,
            modules={'models': ['models.models']}
        )
        await Tortoise.generate_schemas()

    async def load_state(self):
        links = await Link.all()
        return {link.link for link in links}

    def validate_link(self, link):
        return (
            5 <= len(link) <= 32 and
            link[0].isalpha() and
            not (link.startswith('_') or link.endswith('_')) and
            re.match(r'^[a-zA-Z0-9_]+$', link)
        )

    async def read_links_from_file(self):
        with open(self.input_filename, 'r', encoding='utf-8') as f:
            for line in f:
                link = line.strip()
                if self.validate_link(link):
                    yield f"https://t.me/{link}"

    async def check_link(self, session, link):
        try:
            headers = {
                'User-Agent': fake.firefox(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Sec-GPC': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
            async with session.get(link, headers=headers) as response:
                text = await response.text()
                if response.status == 200:
                    if 'noindex, nofollow' in text and '<meta property="og:title" content="Telegram: Contact' in text:
                        return link, 'not_found'
                    if 'class="tgme_page_context_link_wrap"' in text:
                        return link, 'channel'
                    if 'members' in text:
                        return link, 'chat'
                    else:
                        return link, 'account'
                else:
                    print(f'Status {response.status} detected for {link}!')
                    return link, 'error'
        except aiohttp.ClientError as e:
            print(f"Network error occurred while checking link: {link}. Error: {e}")
            return link, 'error'
        except Exception as e:
            print(f"Error occurred while checking link: {link}. Error: {e}")
            return link, 'error'

    async def process_links(self):
        self.checked_links = await self.load_state()
        links = [link async for link in self.read_links_from_file()]
        total_links = len(links)

        self.total_valid_links = 0
        self.total_accounts = 0
        self.total_channels = 0
        self.total_chats = 0
        self.total_not_found = 0
        self.total_errors = 0

        pbar = tqdm_asyncio(total=total_links, desc="Проверка ссылок | Ctrl+C для прекращения")

        async with aiohttp.ClientSession() as session:
            tasks = []
            try:
                for link in links:
                    if link in self.checked_links:
                        continue

                    tasks.append(self.check_link(session, link))
                    self.checked_links.add(link)
                    pbar.update(1)
                    self.total_valid_links += 1

                    if len(tasks) >= 70:
                        await self.save_state()
                        results = await asyncio.gather(*tasks)
                        await self.process_batch(results)
                        tasks = []

                if tasks:
                    await self.save_state()
                    results = await asyncio.gather(*tasks)
                    await self.process_batch(results)

            except asyncio.CancelledError or KeyboardInterrupt:
                print("Процесс прерван. Сохранение состояния...")
                await self.save_state()
                pbar.close()
                raise
            finally:
                pbar.close()


        with open("statistics.txt", "w") as f:
            f.write(f"Total links in dictionary: {total_links}\n")
            f.write(f"Total valid links processed: {self.total_valid_links}\n")
            f.write(f"Total accounts: {self.total_accounts}\n")
            f.write(f"Total channels: {self.total_channels}\n")
            f.write(f"Total chats: {self.total_chats}\n")
            f.write(f"Total not found: {self.total_not_found}\n")
            f.write(f"Total errors: {self.total_errors}\n")

    async def process_batch(self, results):
        async with self.stat_lock:
            with open(self.account_file, "a") as f_accounts, open(self.channel_file, "a") as f_channels, open(self.chat_file, "a") as f_chats, open(self.not_found_file, "a") as f_not_found:
                for link, link_type in results:
                    if link_type == 'account':
                        f_accounts.write(link + "\n")
                        self.total_accounts += 1
                    elif link_type == 'channel':
                        f_channels.write(link + "\n")
                        self.total_channels += 1
                    elif link_type == 'chat':
                        f_chats.write(link + "\n")
                        self.total_chats += 1
                    elif link_type == 'not_found':
                        f_not_found.write(link + "\n")
                        self.total_not_found += 1
                    elif link_type == 'error':
                        print(f"Error checking link: {link}")
                        self.total_errors += 1

    async def save_state(self):
        await Link.filter().delete()
        await Link.bulk_create([Link(link=link) for link in self.checked_links], batch_size=1000)


async def main():
    checker = LinkChecker("links.txt")
    await checker.init_db()
    try:
        await checker.process_links()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(main())
