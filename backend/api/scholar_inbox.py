# File only contains function to fetch papers from Scholar Inbox
# Returns pdf files
# Lot more comments in this file than usual to help 

# DEBUGGING: If scraping isn't working, first suspect is the CSS selectors used to find elements. Do control-F in this file and search for "NOTE TO USER" comments for places where selectors may need to be updated.

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Tag
import time 
import json
import aiohttp
import re
import urllib.request
import feedparser

async def fetch_scholar_inbox_papers(login_url, amount_of_papers):
    async with async_playwright() as p:
        base_url = login_url

        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(base_url)

        await page.wait_for_url('https://scholar-inbox.com', timeout=25000)
        print("Page loaded.")

        try:
            await page.wait_for_selector("main", timeout=25000)
        except Exception:
            print("Timeout waiting for content to load.")
            await browser.close()
            return None

        time.sleep(5)  # Extra wait to ensure content is fully loaded   

        rendered_html = await page.content()
        await browser.close()
        soup = BeautifulSoup(rendered_html, 'html.parser')


        # Get all parent containers. Parent container has title, link, and relevance info
        paper_containers = soup.select('div.MuiBox-root.css-vfiehx') # NOTE TO USER: selector is too general, but it seems to work for now. If scraping isn't working this is def a line to look at. 

        arxiv_links = []

        for container in paper_containers:
            # This var has the title and the link to paper
            link_tag = container.select_one('a[href^="https://arxiv.org/pdf/"].css-wnc5pm') # NOTE TO USER: "css-wnc5pm" is a class that may change, so if scraping breaks, check if this class is still valid. If not, update it to the current class used for arXiv links.
            
            # var has the relevance info
            relevance_tag = container.select_one('div.MuiStack-root.css-2041sb span') # NOTE TO USER: same deal with "css-2041sb", may change over time.
            
            if link_tag:
                url = link_tag.get('href')
                title = link_tag.text.strip()
                relevance = int(relevance_tag.text.strip()) if relevance_tag else "N/A"
                arxiv_id = None
                if url and isinstance(url, str):
                    arxiv_id_match = re.search(r'pdf/(\d+\.\d+)', url)
                    if arxiv_id_match:
                        arxiv_id = arxiv_id_match.group(1)

                        arxiv_links.append({
                            "id": arxiv_id,
                            "title": title,
                            "relevance": relevance,
                            "scraped_url": url
                        })
        
        # Deduping
        arxiv_links = [json.loads(d) for d in set(json.dumps(item, sort_keys=True) for item in arxiv_links)]

        # Ordering by relevance
        arxiv_links.sort(key=lambda x: x['relevance'], reverse=True)

        if (type(amount_of_papers) != str): # str means too keep all, not str means that theres a limit
            if (len(arxiv_links) > amount_of_papers):
                arxiv_links = arxiv_links[:amount_of_papers] 

        # Downloading PDFs from ArXiv API
        print(f"Found {len(arxiv_links)} papers. Starting API fetch and download")

        # Change this to append PDF bytes to arxiv_links dicts
        ids = [d['id'] for d in arxiv_links]
        ids_str = ','.join(ids) 
        url = f'http://export.arxiv.org/api/query?id_list={ids_str}'

        data = None
        with urllib.request.urlopen(url) as response:
            data = response.read()

        feed = feedparser.parse(data)
        
        # async session to download PDFs
        async with aiohttp.ClientSession() as session:
            for entry in feed.entries:
                arxiv_id = entry.id.split('/abs/')[-1]
                
                pdf_url = None
                for link in entry.links:
                    if link.rel == 'related' and link.type == 'application/pdf' and link.title == 'pdf':
                        pdf_url = link.href
                        break

                for paper in arxiv_links:
                    if paper['id'] in arxiv_id: 
                        paper['pdf_url'] = pdf_url
                        
                        if pdf_url:
                            try:
                                async with session.get(pdf_url) as resp:
                                    if resp.status == 200:
                                        paper['pdf_content'] = await resp.read()
                                    else:
                                        print(f"Failed to download {paper['id']}")
                                        paper['pdf_content'] = None
                            except Exception as e:
                                print(f"Error downloading {paper['id']}: {e}")
                                paper['pdf_content'] = None

        cleaned_arxiv_links = [paper for paper in arxiv_links if 'pdf_content' in paper and paper['pdf_content'] is not None]

        print("cleaned arxiv links returned")
        return cleaned_arxiv_links