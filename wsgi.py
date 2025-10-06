#!/usr/bin/env python3
"""
WSGI entry point for production deployment.

This file can be used with WSGI servers like Gunicorn or uWSGI.

Example usage with Gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
"""

from app import app

if __name__ == "__main__":
    app.run()
