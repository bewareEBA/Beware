import asyncio
import string
import re
from typing import List
from urllib.parse import urlparse
import aiofiles
from rich.console import Console
from rich.progress import track
from rich.table import Table

console = Console()

class TelegramLinkGenerator:

    def __init__(self, input_filepath: str = None):
        self.input_filepath = input_filepath
        self.keywords = self._extract_keywords_from_file()
        self._valid_chars = string.ascii_lowercase + string.digits + "_"

    def _is_valid_link(self, link: str) -> bool:
        username = urlparse(link).path.lstrip('/')
        return not (username.startswith('_') or username.endswith('_') or username[0].isdigit())

    async def _read_links_from_file(self) -> List[str]:
        if not self.input_filepath:
            return []
        try:
            async with aiofiles.open(self.input_filepath, mode='r') as f:
                lines = await f.readlines()
                return [line.strip() for line in lines if line.strip()]
        except FileNotFoundError:
            console.print(f"[bold red]Error: File {self.input_filepath} not found.")
            return []
        except Exception as e:
            console.print(f"[bold red]Error reading file: {e}")
            return []


    def _extract_keywords(self, links: List[str]) -> List[str]:
        keywords = set()
        for link in links:
            username = self._extract_username(link)
            if username:
                keywords.update(username.split("_"))
                keywords.update(username.split("-"))
                keywords.update(re.findall(r'\b\w+\b', username))
        return list(keywords)


    def _extract_username(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            if parsed.netloc == "t.me":
                return parsed.path.lstrip("/")
            else:
                return None
        except Exception:
            return None


    def generate_variants(self, keyword: str, max_numeric_suffix: int = 9) -> List[str]:
        variants = []
        if self._is_valid_link(keyword):
            variants.append(f"{keyword}")
        for i in range(1, max_numeric_suffix + 1):
            variants.append(f"{keyword}{i}")
        return variants


    async def generate_all_links(self, max_variants_per_keyword) -> List[str]:
        tasks = [self.generate_variants(keyword) for keyword in self.keywords]
        variants = []
        for task in tasks:
            variants.extend(task)
        return list(set(variants))[:max_variants_per_keyword]



    async def _extract_keywords_from_file(self) -> List[str]:
        links = await self._read_links_from_file()
        return self._extract_keywords(links)



    async def _extract_keywords_from_file(self) -> List[str]:
      links = await self._read_links_from_file()
      return self._extract_keywords(links)



    async def save_links_to_file(self, filepath: str, links: List[str]):
        try:
            async with aiofiles.open(filepath, mode='w') as f:
                await f.writelines(['https://t.me/' + link + '\n' for link in links]) # если нужно с https://t.me/ заменить на await f.writelines(['https://t.me/' + link + '\n' for link in links])
        except Exception as e:
            console.print(f"[bold red]Error saving links to file: {e}")


async def main():
    input_filepath = "links.txt" # файл с ссылками, на основе которых новые генерируются
    output_filepath = "links_generated.txt"# файл с сгенерированными ссыоками

    generator = TelegramLinkGenerator(input_filepath)

    with console.status("[bold green]Reading links from file..."):
        generator.keywords = await generator._extract_keywords_from_file()

    console.print(f"[bold blue]Found {len(generator.keywords)} keywords.")

    with console.status("[bold green]Generating links..."):
        generated_links = await generator.generate_all_links(max_variants_per_keyword=1000000) # заменить 1500 на нужное количество ссылок

    console.print(f"[bold blue]Generated {len(generated_links)} unique links.")

    table = Table(title="Generated Links (First 10)")
    table.add_column("Link", style="cyan")
    for link in generated_links[:10]:
        table.add_row(link)
    console.print(table)

    with console.status("[bold green]Saving links to file..."):
        await generator.save_links_to_file(output_filepath, generated_links)

    console.print(f"[bold green]Links saved to {output_filepath}")



if __name__ == "__main__":
    asyncio.run(main())
