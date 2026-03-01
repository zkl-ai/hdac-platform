# HDAC Platform (Open Source)

A comprehensive platform for heterogeneous device management, model deployment, and monitoring.

## Directory Structure

- `apps/backend`: Flask-based backend service providing REST APIs for device management, task scheduling, and model operations.
- `apps/frontend`: Vue 3 + Ant Design Vue frontend (Monorepo) for the web interface.
- `infra/edge`: Edge device scripts and tools (specifically for NVIDIA Jetson devices).
- `infra/monitor`: Prometheus monitoring configuration for cluster metrics.
- `tools`: Utility scripts for various maintenance tasks.
- `scripts`: Root level scripts for platform initialization and checks.
- `database`: Database schema and migrations.

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ & pnpm (for local development)

### Quick Start (Docker)

1.  Clone the repository.
2.  Navigate to the root directory.
3.  Run the following command to start all services (Backend, Frontend, Database):
    ```bash
    docker-compose up --build
    ```
4.  Access the platform at `http://localhost`.
    - Backend API: `http://localhost:5088`
    - Database: Exposed on port 3306 (user: root, password: rootpassword)

### Local Development

#### Backend

1.  Navigate to `apps/backend`:
    ```bash
    cd apps/backend
    ```
2.  Create a virtual environment and activate it:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configure environment variables in `app/config.py` or `.env`.
5.  Run the application:
    ```bash
    python run.py
    ```

#### Frontend

1.  Navigate to `apps/frontend`:
    ```bash
    cd apps/frontend
    ```
2.  Install dependencies (using pnpm):
    ```bash
    pnpm install
    ```
3.  Start the development server:
    ```bash
    pnpm dev
    ```

## Configuration

- **Database**: The default configuration uses a local MySQL instance. Modify `apps/backend/app/config.py` or set `DATABASE_URL` environment variable to change it.
- **Edge Devices**: Configure default device passwords via `DEFAULT_DEVICE_PASSWORD` environment variable for the backend.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
