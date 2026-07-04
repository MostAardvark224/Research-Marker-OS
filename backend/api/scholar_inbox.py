import imaplib
import email
import re
import urllib.parse
import urllib.request
import feedparser
import aiohttp
from bs4 import BeautifulSoup

# DEBUGGING: If scraping isn't working, first suspect is the CSS selectors or Regex used to find elements.
# Do control-F in this file and search for "NOTE TO USER" comments for places where selectors may need to be updated.


def _decode_html_payload(part) -> str:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="ignore")


def _close_mail_connection(mail):
    try:
        mail.close()
    except Exception:
        pass
    try:
        mail.logout()
    except Exception:
        pass


def _normalize_amount(amount_of_papers):
    if amount_of_papers in (None, "all", ""):
        return None
    if isinstance(amount_of_papers, int) and amount_of_papers > 0:
        return amount_of_papers
    if isinstance(amount_of_papers, str) and amount_of_papers.isdigit():
        return int(amount_of_papers)
    return None


async def fetch_scholar_inbox_papers(env_vars, amount_of_papers=None):
    # 1. Connect to Gmail via IMAP (Must use SSL for Gmail)
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    email_addr = str(env_vars.get("scholar_inbox_email", ""))
    password = str(env_vars.get("gmail_app_password", ""))

    if not email_addr or not password:
        print("Scholar Inbox Gmail credentials not configured.")
        return []

    try:
        mail.login(email_addr, password)
    except imaplib.IMAP4.error as e:
        print(f"Login failed: {e}")
        return []

    try:
        mail.select("INBOX", readonly=True)

        # 2. Search for the latest email from noreply@cvlibs.net with "Alert Digest" in the subject
        print("Searching for Alert Digest email...")
        search_criteria = '(FROM "noreply@cvlibs.net" SUBJECT "Alert Digest")'
        status, data = mail.search(None, search_criteria)

        if status != "OK" or not data or not data[0]:
            print("No 'Alert Digest' emails found in inbox.")
            return []

        mail_ids = data[0].split()
        if not mail_ids:
            print("No 'Alert Digest' emails found in inbox.")
            return []

        latest_id = mail_ids[-1]

        # 3. Fetch the email content
        status, data = mail.fetch(latest_id, "(RFC822)")
        if status != "OK" or not data or not data[0]:
            print("Failed to fetch Alert Digest email.")
            return []

        fetch_result = data[0]
        if not isinstance(fetch_result, tuple) or len(fetch_result) < 2:
            print("Unexpected email fetch response format.")
            return []

        raw_email = fetch_result[1]
        if not isinstance(raw_email, bytes):
            print("Email body was not bytes.")
            return []

        msg = email.message_from_bytes(raw_email)

        # 4. Extract the HTML body from the email
        html_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = _decode_html_payload(part)
                    break
        elif msg.get_content_type() == "text/html":
            html_content = _decode_html_payload(msg)

        if not html_content:
            print("Could not find HTML content in the email.")
            return []

        # 5. Parse the email HTML using BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # NOTE TO USER: We look for <a> tags where the href contains "scholar-inbox.com/login".
        # If the email format changes, adjust this regex pattern.
        paper_links = soup.find_all("a", href=re.compile(r"scholar-inbox\.com/login"))

        extracted_papers = []
        for link in paper_links:
            title = link.text.strip()
            title = re.sub(r"\s+", " ", title)

            if title:
                extracted_papers.append(
                    {
                        "title": title,
                        "scraped_url": link.get("href"),
                    }
                )

        seen_titles = set()
        unique_papers = []
        for paper in extracted_papers:
            if paper["title"] not in seen_titles:
                seen_titles.add(paper["title"])
                unique_papers.append(paper)

        paper_limit = _normalize_amount(amount_of_papers)
        if paper_limit is not None:
            unique_papers = unique_papers[:paper_limit]

        print(f"Found {len(unique_papers)} unique papers in the email. Searching arXiv API by title...")

        # 6. Search the arXiv API using the extracted titles
        arxiv_links = []
        for paper in unique_papers:
            encoded_title = urllib.parse.quote(f'ti:"{paper["title"]}"')
            query_url = f"http://export.arxiv.org/api/query?search_query={encoded_title}&max_results=1"

            try:
                with urllib.request.urlopen(query_url) as response:
                    feed_data = response.read()

                feed = feedparser.parse(feed_data)

                if feed.entries:
                    entry = feed.entries[0]
                    entry_id = str(entry.get("id", ""))
                    arxiv_id = entry_id.split("/abs/")[-1]

                    pdf_url = None
                    for link in entry.links:
                        if link.rel == "related" and link.type == "application/pdf":
                            pdf_url = link.href
                            break

                    if not pdf_url:
                        pdf_url = entry_id.replace("/abs/", "/pdf/")

                    paper["id"] = arxiv_id
                    paper["pdf_url"] = pdf_url
                    arxiv_links.append(paper)
                else:
                    print(f"Could not find arXiv match for: {paper['title']}")
            except Exception as e:
                print(f"Error querying arXiv for '{paper['title']}': {e}")

        # 7. Download PDFs asynchronously
        print(f"Starting API fetch and download for {len(arxiv_links)} matched papers...")

        async with aiohttp.ClientSession() as session:
            for paper in arxiv_links:
                pdf_url = paper.get("pdf_url")
                if not pdf_url:
                    continue

                try:
                    async with session.get(pdf_url) as resp:
                        if resp.status == 200:
                            paper["pdf_content"] = await resp.read()
                        else:
                            print(f"Failed to download {paper['id']} (Status: {resp.status})")
                            paper["pdf_content"] = None
                except Exception as e:
                    print(f"Error downloading {paper.get('id', 'unknown')}: {e}")
                    paper["pdf_content"] = None

        cleaned_arxiv_links = [
            paper for paper in arxiv_links if paper.get("pdf_content") is not None
        ]

        print(f"Returning {len(cleaned_arxiv_links)} papers with downloaded PDFs.")
        return cleaned_arxiv_links
    finally:
        _close_mail_connection(mail)
