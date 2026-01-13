<div align="center">

<div align="center">
  <img src="frontend/public/logo.svg" alt="Research Marker" width="80" />
  <h1>Research Marker</h1>
  <br />
</div>
  <p>
    <strong>Consolidate your knowledge base in one central, queryable location.</strong>
  </p>

  <p>
    Research Marker is an open-source research annotation platform designed to streamline your workflow. Never lose a research paper again.
  </p>

  <p>
    <sub>Created by <a href="https://github.com/MostAardvark224">Amay Babel</a></sub>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Status-Active_Development-success?style=flat-square" alt="Status" />
    <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License" />
  </p>

  <br />
  <h3>
    🚧 Full documentation and downloads for Windows, Mac, and Linux are coming very soon! 🚧
  </h3>
  <br />

</div>

---

## 💡 Why Research Marker?

I built Research Marker to solve the fragmentation of modern research.

Currently, students and researchers have to juggle PDFs in local folders, citations in browser tabs, and notes in separate apps. Research Marker unifies this process. It allows you to:

- **Automate** your paper reading workflows.
- **Centralize** every paper you read.
- **Annotate** directly on the document without modifying the source file.
- **Query** your own knowledge base to find connections between papers instantly.

---

## ✨ Features

- **📥 Smart Ingestion:** Seamlessly upload your research PDFs and automatically apply OCR to make every document searchable and annotatable.

- **📄 PDF Annotation:** Highlight, underline, and add sticky notes to your research papers.

- **🤖 Intelligent Search & AI Analysis:** Leverage high-quality search features and context-aware AI to query your library in natural language.

- **🕸️ Semantic Linking:** Visualize your ideas in an easy-to-digest graph format, showing connections between concepts and recommendations for new topic areas.

- **🔍 Full-Text Search:** Instantly find ideas by leveraging our smart-search system to discover concepts within papers, notes, and folders.

- **🏷️ Smart Tagging:** Organize your research by topic, class, or project with a flexible tagging system.

- **📂 Offline Capabilities:** Annotate research on-the-go with our desktop app.

- **⚡ Modern UI:** Built for speed and readability, ensuring you focus on the content, not the tool.

- **🎓 Scholar Inbox Integration:** Automatically import your daily digest from Scholar Inbox, ready for you to annotate today's cutting-edge work.

Build commands:
Backend (cd into the backend dir and activate the venv):
rm -rf dist build && pyinstaller api.spec --noconfirm --clean

Frontend (cd into the frontend dir):
pnpm run build
