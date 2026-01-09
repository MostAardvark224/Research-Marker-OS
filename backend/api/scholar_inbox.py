# File only contains function to fetch papers from Scholar Inbox
# Returns pdf files
# Lot more comments in this file than usual to help 

# DEBUGGING: If scraping isn't working, first suspect is the CSS selectors used to find elements. Do control-F in this file and search for "NOTE TO USER" comments for places where selectors may need to be updated.

# DEBUGGING: If your getting playwright errors, check and make sure that you have browser binaries installed. if not, just run "playwright install" in your terminal, or download one of google chrome, edge, opera, or brave
# SAFARI ALONE WONT WORK WITH PLAYWRIGHT. 

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Tag
import time 
import json
import aiohttp
import re
import urllib.request
import feedparser
import sys
import os
import subprocess
import shutil

if sys.platform == "win32":
    import winreg

# gets the browser path for the users machine
# I have to do this for js scraping scholar inbox
def get_browser_path():
    if sys.platform == "win32":
        return _find_windows_browser()
    elif sys.platform == "darwin":
        return _find_mac_browser()
    elif sys.platform == "linux":
        return _find_linux_browser()
    return None

"""
Looks for any of the following browsers (windows)

"Microsoft Edge", 
"Google Chrome", 
"Brave", 
"OperaStable"  
"""
def _find_windows_browser():
    reg_path = r"SOFTWARE\Clients\StartMenuInternet"
    
    browser_keys = [
        "Microsoft Edge", 
        "Google Chrome", 
        "Brave", 
        "OperaStable"  
    ]

    if sys.platform == "win32":
        for browser in browser_keys:
            try:
                # Look in HKEY_LOCAL_MACHINE
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{reg_path}\\{browser}\\shell\\open\\command") as key:
                    cmd, _ = winreg.QueryValueEx(key, "")
                    return cmd.strip('"')
            except OSError:
                # If system-wide fails, try HKEY_CURRENT_USER 
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{reg_path}\\{browser}\\shell\\open\\command") as key:
                        cmd, _ = winreg.QueryValueEx(key, "")
                        return cmd.strip('"')
                except OSError:
                    continue

    return None

"""
Looks for any of the following browsers (mac)

"Microsoft Edge", 
"Google Chrome", 
"Brave", 
"OperaStable"  
"""
def _find_mac_browser():
    bundle_ids = {
        "com.google.Chrome": "/Contents/MacOS/Google Chrome",
        "com.microsoft.edgemac": "/Contents/MacOS/Microsoft Edge",
        "com.brave.Browser": "/Contents/MacOS/Brave Browser",
        "com.operasoftware.Opera": "/Contents/MacOS/Opera"  
    }

    for bundle_id, inner_path in bundle_ids.items():
        try:
            output = subprocess.check_output(
                ["mdfind", f"kMDItemCFBundleIdentifier == '{bundle_id}'"],
                encoding="utf-8"
            ).strip()

            if output:
                app_path = output.split('\n')[0]
                full_path = app_path + inner_path
                if os.path.exists(full_path):
                    return full_path
        except subprocess.CalledProcessError:
            continue

    return None

"""
Looks for any of the following browsers (linux)

"Microsoft Edge", 
"Google Chrome", 
"Brave", 
"OperaStable", 
"Chromium
"""
def _find_linux_browser():
    commands = [
        "google-chrome", 
        "microsoft-edge", 
        "chromium", 
        "brave-browser",
        "opera",         
        "opera-stable"   
    ]
    
    for cmd in commands:
        path = shutil.which(cmd)
        if path:
            return path
    return None

async def fetch_scholar_inbox_papers(login_url, amount_of_papers):
    async with async_playwright() as p:
        base_url = login_url
        browser_path = get_browser_path()

        if not browser_path:
            # Handle the error gracefully for the user
            raise FileNotFoundError("No supported browser (Chrome, Edge, Opera, or Brave) found on this system.")

        browser = await p.chromium.launch(executable_path=browser_path, headless=True)
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
                arxiv_id = entry.id.split('/abs/')[-1] # type: ignore
                
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
                                async with session.get(pdf_url) as resp: # type: ignore
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