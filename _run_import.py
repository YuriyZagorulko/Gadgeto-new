#!/usr/bin/env python3
"""Run DC-Link import script."""
import sys
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv('.env')

from app.imports.tasks import run_import
import time

print('=' * 70)
print('DC-LINK FULL IMPORT - Brand Backfill')
print('=' * 70)
print()

start = time.time()
result = run_import('dclink', 'full')
elapsed = time.time() - start

print()
print('=' * 70)
print(f'Completed in {elapsed:.1f}s')
print('Result:', result)
print('=' * 70)
