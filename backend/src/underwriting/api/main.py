"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from underwriting.api.db import init_db
from underwriting.api.rate_limit import RateLimitMiddleware
from underwriting.api.routers import cases, health
from underwriting.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Mortgage Underwriting API",
    description="Multi-agent underwriting workflow: submission, retrieval, and human review.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst=20)

app.include_router(health.router)
app.include_router(cases.router)
