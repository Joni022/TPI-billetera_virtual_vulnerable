FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-bookworm AS python-base
WORKDIR /app
COPY requirements.txt requirements.lock.txt ./
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install --no-cache-dir -r requirements.lock.txt
RUN useradd --uid 10001 --create-home wallet

FROM python-base AS browser-base
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright

FROM python-base AS runtime
COPY backend/ backend/
COPY fixtures/ fixtures/
COPY --from=frontend-build /frontend/dist frontend/dist/
USER 10001:10001
CMD ["python", "-m", "backend.main"]

FROM browser-base AS lab
COPY backend/ backend/
COPY fixtures/ fixtures/
COPY --from=frontend-build /frontend/dist frontend/dist/
COPY lab/ lab/
COPY tests_browser/ tests_browser/
USER 10001:10001
CMD ["python", "-m", "lab.main"]
