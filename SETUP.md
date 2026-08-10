# ArchgenCAD Setup Guide

This guide covers the complete setup process for ArchgenCAD on both Windows and Linux, from prerequisites to running the application.

## 1. Prerequisites

Before starting, ensure you have the following installed:
- **Python 3.10+**
- **Node.js 18+**
- **FreeCAD 1.0** (See installation instructions below)

## 2. FreeCAD Installation

### Windows
1. Download the FreeCAD 1.0 installer from the [official releases page](https://github.com/FreeCAD/FreeCAD/releases).
2. Run the installer and follow the on-screen instructions.
3. Ensure the installation path is accessible (e.g., `C:\Program Files\FreeCAD 1.0`).
4. The backend must be configured to locate the FreeCAD `bin` directory (usually handled via environment variables or path updates).

### Linux (Ubuntu/Debian)
Install FreeCAD 1.0 using the official PPA or apt:
```bash
sudo add-apt-repository ppa:freecad-maintainers/freecad-stable
sudo apt-get update
sudo apt-get install freecad
```
Verify the installation by running `freecadcmd --version`.

## 3. Python Virtual Environment Setup

Navigate to the project root and create a Python virtual environment:

### Windows
```cmd
python -m venv venv
venv\Scripts\activate
```

### Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

## 4. Install Backend Dependencies

With the virtual environment activated, install the required Python packages:
```bash
pip install -r requirements.txt
```

## 5. Pinecone Setup

ArchgenCAD uses Pinecone as a vector database for semantic search and retrieval.
1. Go to [Pinecone](https://www.pinecone.io/) and create a free account.
2. Obtain your API key from the dashboard.
3. Create a new Index with the following settings:
   - **Index Name:** `archgencad`
   - **Dimensions:** `384`
   - **Metric:** `cosine`

## 6. OpenRouter Setup

OpenRouter provides access to various LLMs.
1. Create an account at [OpenRouter](https://openrouter.ai/).
2. Generate an API key.
3. ArchgenCAD uses model routing to select the appropriate model for different tasks. Ensure your account is funded or you have access to the free models specified in the code.

## 7. Cohere Setup

Cohere is used for embeddings and reranking.
1. Create an account at [Cohere](https://cohere.com/).
2. Obtain your API key. The free tier is sufficient for standard usage (embeddings and reranking).

## 8. Environment Configuration

Copy the example environment file and configure it with your API keys:

### Backend
```bash
cp .env.example .env
```
Edit `.env` and fill in:
- `PINECONE_API_KEY`
- `OPENROUTER_API_KEY`
- `COHERE_API_KEY`
- Other necessary variables as listed in the file.

### Frontend
```bash
cd web/app
cp .env.example .env.local
```
Edit `web/app/.env.local` to point to your backend if not using localhost.

## 9. Clients Setup

Configure allowed clients/users for the backend:
```bash
cp clients.example.json clients.json
```
Edit `clients.json` to add user credentials and permissions as needed.

## 10. Initialize Pinecone

Populate the Pinecone index with sample data or initial vectors:
```bash
# Ensure you are in the project root with the virtual environment activated
python migrate_to_pinecone.py
```

## 11. Create Runtime Directories

Ensure the directories required by the backend for storing temporary files, logs, and generated CAD files exist:
```bash
mkdir -p data logs output tmp
```
*(On Windows, use `mkdir data logs output tmp` in PowerShell/CMD).*

## 12. Start the Backend

Start the FastAPI backend server:

### Windows
```cmd
start_backend.bat
```

### Linux
```bash
bash start_backend.sh
```

## 13. Frontend Setup

In a new terminal window, start the frontend development server:
```bash
cd web/app
npm install
npm run dev
```
The frontend will be accessible at `http://localhost:5173` (or as specified by Vite).

## 14. Production Setup Notes

For deploying ArchgenCAD to a production environment:
- **Docker:** Use the provided Dockerfiles to build images for the frontend and backend. Docker Compose can orchestrate the services.
- **Nginx:** Set up Nginx as a reverse proxy to route traffic to the frontend and backend (e.g., `/api` to the backend, `/` to the frontend).
- **SSL:** Secure your deployment with SSL certificates using Let's Encrypt / Certbot.
- **Process Management:** Use PM2 (Node.js) or Gunicorn/Uvicorn (Python) with systemd to manage production processes.

## 15. Troubleshooting

### FreeCAD not found error
- **Issue:** The backend cannot import the `FreeCAD` module.
- **Fix:** Ensure the FreeCAD `bin` or `lib` directory is added to your system's `PATH` or `PYTHONPATH`. On Windows, this is typically `C:\Program Files\FreeCAD 1.0\bin`.

### Pinecone connection errors
- **Issue:** Connection timeout or unauthorized errors when accessing Pinecone.
- **Fix:** Verify your `PINECONE_API_KEY` and ensure the index name exactly matches `archgencad`. Check your internet connection or corporate firewall.

### Memory issues on small instances
- **Issue:** Process gets killed (OOM) during heavy CAD operations or embedding generation.
- **Fix:** Ensure your machine/server has at least 4GB of RAM. If using an EC2 micro instance, configure a swap file (at least 2GB).

### Windows-specific DLL issues
- **Issue:** Missing DLL errors when starting FreeCAD via Python.
- **Fix:** Install the latest Microsoft Visual C++ Redistributable. Ensure Python architecture (64-bit) matches FreeCAD architecture.
