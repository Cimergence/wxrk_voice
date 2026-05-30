# wxrk_voice

Voice interface module for the WXRK platform.

## Overview

This service provides voice input and output capabilities, enabling users to interact with WXRK features through speech.

## Stack

- **Python** — core service logic
- **Docker** — containerized deployment

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose

### Run with Docker

```bash
docker compose up --build
```

### Run locally

```bash
pip install -r requirements.txt
python main.py
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```
