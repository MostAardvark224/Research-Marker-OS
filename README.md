<div align="center">

  <img src="frontend/public/logo.svg" alt="Research Marker" width="80" />
  <h1>Research Marker</h1>

  <a href="https://research-marker.web.app/">
    <b>Download</b>
  </a>

  <br />
  <br />

  <p>
    An open-source desktop app for reading, annotating, and querying your research library.
  </p>

  <p>
    <sub>Created by <a href="https://github.com/MostAardvark224">Amay Babel</a></sub>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Status-Active_Development-success?style=flat-square" alt="Status" />
    <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License" />
  </p>

</div>

---

## Overview

Research papers tend to end up spread across folders, browser tabs, and separate note apps. Research Marker keeps the library, annotations, and search in one local desktop app so you can read, mark up, and ask questions against the same corpus.

---

## Features

### Library

- Import local PDFs by drag and drop
- Paste an arXiv link to fetch the title, metadata, and PDF
- Connect Gmail to import papers from Scholar Inbox digests
- Organize papers in nested folders with drag and drop and custom reading order
- Restore the last page and zoom level when reopening a paper

### Reading and annotation

- Multi-page PDF viewer for longer reading sessions
- Color-coded highlights with a customizable palette
- Sticky notes anchored to a page, with optional tags (Definition, Question, Insight, Critique, Evidence)
- Per-paper notepad with math formatting
- Toggle annotations, search within the document, and keyboard shortcuts for common actions

### AI chat

- Use your own API keys with Claude, ChatGPT, Gemini, or OpenRouter
- Sign in with ChatGPT to use the embedded Codex runtime for paper-grounded answers without a separate API key
- Chat about the open paper or across the full library
- Point the model at specific context with `@` tags such as `@page`, `@highlights`, and `@paper`
- Answers are grounded in your papers and notes, with citations back to those sources

### Topic graph

- Build an interactive graph that groups related papers from your notes and library
- Inspect overlaps between authors and concepts across subfields
- Get cluster overviews and suggestions for what to read next

### Search

- Search titles, highlights, sticky notes, and notepads in one place
- Run OCR on scanned PDFs so text can be selected and indexed
- Filter results by recent notes, tags, or folders

### Privacy and platforms

- Native desktop app for Mac, Windows, and Linux
- Papers, reading history, notes, and API keys stay on your machine
- Core reading and annotation work offline
- Background updates keep the app current without interrupting your session
