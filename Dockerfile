# Multi-stage build for smaller image
FROM node:20-slim as frontend-builder

# Build React frontend
WORKDIR /app/frontend-react
COPY frontend-react/package*.json ./
RUN npm ci

COPY frontend-react/ ./

# Ensure src/lib directory exists and has utils.ts
RUN mkdir -p src/lib && \
    if [ ! -f src/lib/utils.ts ]; then \
        echo "Creating missing utils.ts file" && \
        printf 'import { clsx, type ClassValue } from "clsx"\nimport { twMerge } from "tailwind-merge"\n\nexport function cn(...inputs: ClassValue[]) {\n  return twMerge(clsx(inputs));\n}\n' > src/lib/utils.ts; \
    fi

RUN npm run build

# Python dependencies builder
FROM python:3.11-slim as python-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies including Node.js for any runtime needs
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    netcat-traditional \
    sqlite3 \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxcb1 \
    libxss1 \
    libgtk-3-0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=python-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy entrypoint script first (before copying everything)
COPY docker/entrypoint.sh /entrypoint.sh
# Fix line endings for cross-platform compatibility and make executable
RUN dos2unix /entrypoint.sh 2>/dev/null || sed -i 's/\r$//' /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Copy application code
WORKDIR /app
COPY . .

# Fix line endings for all shell scripts to ensure cross-platform compatibility
RUN find . -type f -name "*.sh" -exec dos2unix {} \; 2>/dev/null || \
    find . -type f -name "*.sh" -exec sed -i 's/\r$//' {} \; && \
    find . -type f -name "*.sh" -exec chmod +x {} \;

# Copy built frontend from frontend builder
COPY --from=frontend-builder /app/frontend-react/dist ./frontend-react/dist

# Install Playwright browsers
RUN playwright install chromium

# Create directories for logs and data
RUN mkdir -p logs logs/error_screenshots logs/error_html data

# Expose port 5001 (standardized)
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Use entrypoint script for database migrations
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "run.py"]
